"""
Test vv.util module
"""
__author__ = 'Dan Gunter <dkgunter@lbl.gov>'

from argparse import ArgumentParser
import unittest
from matgendb.vv.util import JsonWalker, YamlConfig


class Jsonable:
    def __init__(self, s):
        self.value = s

    def as_json(self):
        return "{}zinho".format(self.value)


class MyTestCase(unittest.TestCase):
    
    def setUp(self):
        self.init_yaml()

    ## JsonWalker

    def test_json_walker(self):
        """JsonWalker class.
        """
        doc = {
            "hello": "world",
            "nested.value": 123,
            "funny$$char": [1, 2, 3],
            "listy": [
                {"item": Jsonable("Ciao")}
            ]
        }
        expected = {
            "hello": "world",
            "nested": {"value": 123},
            "funny__char": [1, 2, 3],
            "listy": [
                {"item": "Ciaozinho"}
            ]
        }
        walker = JsonWalker(value_transform=JsonWalker.value_json,
                            dict_transform=JsonWalker.dict_expand)
        result = walker.walk(doc)
        self.assertEqual(expected, result)

    ## YamlConfig

    def init_yaml(self):
        self.y_file = 'test.yaml'
        self.y_name = 'spam'
        self.y_value = 'eggs'
        with open(self.y_file, mode='w') as f:
            f.write('{}: {}'.format(self.y_name, self.y_value))
        self.y_parser = ArgumentParser()
        self.y_parser.add_argument('--config', action=YamlConfig)
        self.y_parser.add_argument('--{}'.format(self.y_name))

    def test_yaml_populate(self):
        """YamlConfig populates args.
        """
        args = self.y_parser.parse_args('--config {}'.format(self.y_file).split())
        assert getattr(args, self.y_name) == self.y_value

    def test_yaml_override(self):
        """YamlConfig arg overrides file, if given last.
        """
        expected = '42'
        args = self.y_parser.parse_args('--config {} --spam {}'
                                        .format(self.y_file, expected).split())
        assert getattr(args, self.y_name) == expected

    def test_yaml_override2(self):
        """YamlConfig file overrides arg, if given last.
        """
        value = 12
        args = self.y_parser.parse_args('--spam {} --config {}'
                                        .format(value, self.y_file).split())
        assert getattr(args, self.y_name) == self.y_value


if __name__ == '__main__':
    unittest.main()
