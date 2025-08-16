from core.template_matcher import TemplateMatcher
from features.base_bar_checker import BaseBarChecker

class ManaChecker(BaseBarChecker):
    def __init__(self, template_path, light_hsv, dark_hsv, bar_match_threshold=0.85):
        super().__init__(
            name="Mana",
            bar_template=TemplateMatcher(template_path, threshold=bar_match_threshold),
            light_hsv=light_hsv,
            dark_hsv=dark_hsv,
            low_threshold=0,           # mana için tuş aksiyonu yok, sadece ölçüm
            key_on_low=None,
            input_controller=None,
            active=True,
            bar_match_threshold=bar_match_threshold,
        )