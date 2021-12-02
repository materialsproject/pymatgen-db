"""
Example builders that read or write files.
"""
__author__ = "Dan Gunter <dkgunter@lbl.gov>"
__date__ = "5/16/14"

from pymatgen.db.builders.core import Builder


class FileCounter(Builder):
    """Count lines and characters in a file."""

    def __init__(self, **kwargs):
        self.num_lines, self.num_chars = 0, 0
        # The flag sequential=True is necessary to
        # allow for the shared variables above. Otherwise,
        # due to parallelism, special procedures would be
        # needed to safely increment shared vars.
        Builder.__init__(self, **kwargs)

    def get_parameters(self):
        return {"input_file": {"type": "str", "desc": "Input file path"}}

    def get_items(self, input_file=None):
        with open(input_file) as f:
            # print("Reading from {}".format(f.name))
            yield from f

    def process_item(self, item):
        self.num_chars += len(item)
        self.num_lines += 1
        # print("{:d} lines, {:d} characters".format(
        #    self.num_lines, self.num_chars))

    def finalize(self, errors):
        print(f"{self.num_lines:d} lines, {self.num_chars:d} characters")
        return True
