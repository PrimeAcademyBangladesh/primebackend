""" Implementation of a strict JSON parser that raises an error on invalid JSON format. """

import json

from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser


class StrictJSONParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        try:
            return super().parse(stream, media_type, parser_context)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON format: {str(e)}")
