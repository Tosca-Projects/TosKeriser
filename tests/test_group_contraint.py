import yaml

from toskeriser.exceptions import TkStackException

from .test_upper import TestUpper


class TestGroupOsError(TestUpper):

    @classmethod
    def setUpClass(self):
        self._file_path = 'data/examples/example_group_constraint.yaml'
        self._new_path = 'data/examples/example_group_constraint.'\
                         'completed.yaml'
        self._mock_responces = {}
        self._node_templates = yaml.load('')

    # TODO: check the specific error
    def test_default(self):
        with self.assertRaises(TkStackException):
            self._default_test()

    def test_policy(self):
        with self.assertRaises(TkStackException):
            self._policy_test()

    def test_constraints(self):
        with self.assertRaises(TkStackException):
            self._constraints_test()
