import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Union, Callable, Optional

from aw_core.models import Event

from .storages import AbstractStorage

logger = logging.getLogger(__name__)


class Datastore:
    def __init__(self, storage_strategy: Callable[..., AbstractStorage], testing=False) -> None:
        self.logger = logger.getChild("Datastore")
        self.bucket_instances = dict()  # type: Dict[str, Bucket]

        self.storage_strategy = storage_strategy(testing=testing)

    def __repr__(self):
        return "<Datastore object using {}>".format(self.storage_strategy.__class__.__name__)

    def __getitem__(self, bucket_id: str) -> "Bucket":
        # If this bucket doesn't have a initialized object, create it
        if bucket_id not in self.bucket_instances:
            # If the bucket exists in the database, create an object representation of it
            if bucket_id in self.buckets():
                bucket = Bucket(self, bucket_id)
                self.bucket_instances[bucket_id] = bucket
            else:
                self.logger.error("Cannot create a Bucket object for {} because it doesn't exist in the database".format(bucket_id))
                raise KeyError

        return self.bucket_instances[bucket_id]

    def create_bucket(self, bucket_id: str, type: str, client: str, hostname: str,
                      created: datetime = datetime.now(timezone.utc), name: Optional[str] = None) -> "Bucket":
        self.logger.info("Creating bucket '{}'".format(bucket_id))
        self.storage_strategy.create_bucket(bucket_id, type, client, hostname, created.isoformat(), name=name)
        return self[bucket_id]

    def delete_bucket(self, bucket_id: str):
        self.logger.info("Deleting bucket '{}'".format(bucket_id))
        if bucket_id in self.bucket_instances:
            del self.bucket_instances[bucket_id]
        return self.storage_strategy.delete_bucket(bucket_id)

    def buckets(self):
        return self.storage_strategy.buckets()


class Bucket:
    def __init__(self, datastore: Datastore, bucket_id: str) -> None:
        self.logger = logger.getChild("Bucket")
        self.ds = datastore
        self.bucket_id = bucket_id

    def metadata(self) -> dict:
        return self.ds.storage_strategy.get_metadata(self.bucket_id)

    def get(self, limit: int = -1,
            starttime: datetime=None, endtime: datetime=None) -> List[Event]:
        """Returns events sorted in descending order by timestamp"""
        # Resolution is rounded down since not all datastores like microsecond precision
        if starttime:
            starttime = starttime.replace(microsecond=1000 * int(starttime.microsecond / 1000))
        if endtime:
            microseconds = 1000 * int(endtime.microsecond / 1000 + 1)
            if microseconds > 999999:
                endtime = endtime.replace(microsecond=0) + timedelta(seconds=1)
            else:
                endtime = endtime.replace(microsecond=microseconds)

        return self.ds.storage_strategy.get_events(self.bucket_id, limit, starttime, endtime)

    def insert(self, events: Union[Event, List[Event]]) -> Union[Event, List[Event]]:
        # NOTE: Should we keep the timestamp checking?
        # Get last event for timestamp check after insert
        last_event_list = self.get(1)
        last_event = None
        if len(last_event_list) > 0:
            last_event = last_event_list[0]

        inserted = None  # type: Union[Event, List[Event]]

        # Call insert
        if isinstance(events, Event):
            oldest_event = events
            inserted = self.ds.storage_strategy.insert_one(self.bucket_id, events)
            assert inserted
        elif isinstance(events, list):
            if len(events) > 0:
                oldest_event = sorted(events, key=lambda k: k['timestamp'])[0]
            else:
                oldest_event = None
            inserted = self.ds.storage_strategy.insert_many(self.bucket_id, events)
            # assert inserted
        else:
            raise TypeError

        # Warn if timestamp is older than last event
        if last_event and oldest_event:
            if oldest_event.timestamp < last_event.timestamp:
                self.logger.warning("Inserting event that has a older timestamp than previous event!" +
                                    "\nPrevious:" + str(last_event) +
                                    "\nInserted:" + str(oldest_event))

        return inserted

    def replace_last(self, event):
        return self.ds.storage_strategy.replace_last(self.bucket_id, event)

    def replace(self, event_id, event):
        return self.ds.storage_strategy.replace(self.bucket_id, event_id, event)
