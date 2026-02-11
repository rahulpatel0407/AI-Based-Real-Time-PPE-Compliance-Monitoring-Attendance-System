import unittest

from violation_logic import is_helmet_violation


class TestViolationLogic(unittest.TestCase):
    def test_violation_requires_overlap(self):
        person_bbox = (10, 10, 110, 210)
        no_helmet_boxes = [(200, 200, 300, 300, 0.9)]
        violated, conf = is_helmet_violation(
            0.95,
            person_bbox,
            no_helmet_boxes,
            [],
            0.45,
            0.45,
            0.5,
            0.1,
        )
        self.assertFalse(violated)
        self.assertEqual(conf, 0.0)

    def test_violation_true_on_overlap(self):
        person_bbox = (10, 10, 110, 210)
        no_helmet_boxes = [
            (50, 40, 90, 120, 0.6),
            (15, 20, 40, 80, 0.7),
        ]
        violated, conf = is_helmet_violation(
            0.8,
            person_bbox,
            no_helmet_boxes,
            [],
            0.45,
            0.45,
            0.5,
            0.1,
        )
        self.assertTrue(violated)
        self.assertAlmostEqual(conf, 0.7, places=3)

    def test_violation_false_when_person_below_threshold(self):
        person_bbox = (10, 10, 110, 210)
        no_helmet_boxes = [(20, 20, 40, 60, 0.9)]
        violated, conf = is_helmet_violation(
            0.4,
            person_bbox,
            no_helmet_boxes,
            [],
            0.45,
            0.45,
            0.5,
            0.1,
        )
        self.assertFalse(violated)
        self.assertEqual(conf, 0.0)

    def test_violation_suppressed_by_hardhat(self):
        person_bbox = (10, 10, 110, 210)
        no_helmet_boxes = [(20, 20, 40, 60, 0.7)]
        hardhat_boxes = [(18, 18, 45, 65, 0.8)]
        violated, conf = is_helmet_violation(
            0.9,
            person_bbox,
            no_helmet_boxes,
            hardhat_boxes,
            0.45,
            0.45,
            0.5,
            0.1,
        )
        self.assertFalse(violated)
        self.assertEqual(conf, 0.0)


if __name__ == "__main__":
    unittest.main()
