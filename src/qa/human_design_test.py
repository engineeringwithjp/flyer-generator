"""Human Design Test assessment tool."""

from src.core.models import FlyerSpecification, QAResult
from src.qa.checker import QAChecker


class HumanDesignTest:
    def __init__(self):
        self.checker = QAChecker()

    def audit(self, spec: FlyerSpecification, rendered_image_path: str) -> QAResult:
        """Runs the complete Human Design Test."""
        return self.checker.evaluate(spec, rendered_image_path)
