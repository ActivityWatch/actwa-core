from typing import Pattern, List, Iterable, Tuple, Dict, Optional, Any
from functools import reduce
import re

from aw_core import Event


Tag = str
Category = List[str]


class Rule:
    regex: Optional[Pattern]
    select_keys: Optional[List[str]]
    ignore_case: bool

    def __init__(self, rules: Dict[str, Any]):
        self.select_keys = rules.get("select_keys", ["app", "title"])
        self.ignore_case = rules.get("ignore_case", False)

        # NOTE: Also checks that the regex isn't an empty string (which would erroneously match everything)
        regex_str = rules.get("regex", None)
        self.regex = (
            re.compile(
                regex_str, (re.IGNORECASE if self.ignore_case else 0) | re.UNICODE
            )
            if regex_str
            else None
        )

    def match(self, e: Event) -> bool:
        # `data` contains keys like 'app', 'title'
        # by default, the rule regex is matched against all values

        if self.select_keys == 'all'
            values = list(e.data.values())
        elif self.select_keys:
            values = [e.data.get(key, None) for key in self.select_keys]

        # although there is a `type` field on the rule name, right now the only valid type is regex
        if self.regex:
            for val in values:
                if isinstance(val, str) and self.regex.search(val):
                    return True
        return False


def categorize(events: List[Event], classes: List[Tuple[Category, Rule]]):
    return [_categorize_one(e, classes) for e in events]


def _categorize_one(e: Event, classes: List[Tuple[Category, Rule]]) -> Event:
    # TODO can we add a color here too? why is color rendered on the frontend?
    e.data["$category"] = _pick_category(
        [_cls for _cls, rule in classes if rule.match(e)]
    )
    return e


def tag(events: List[Event], classes: List[Tuple[Tag, Rule]]):
    return [_tag_one(e, classes) for e in events]


def _tag_one(e: Event, classes: List[Tuple[Tag, Rule]]) -> Event:
    e.data["$tags"] = [_cls for _cls, rule in classes if rule.match(e)]
    return e


def _pick_category(tags: Iterable[Category]) -> Category:
    return reduce(_pick_deepest_cat, tags, ["Uncategorized"])


def _pick_deepest_cat(t1: Category, t2: Category) -> Category:
    # t1 will be the accumulator when used in reduce
    # Always bias against t1, since it could be "Uncategorized"
    return t2 if len(t2) >= len(t1) else t1
