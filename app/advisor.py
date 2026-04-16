from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from .schemas import ChatTurn


@dataclass(frozen=True)
class IntentProfile:
    name: str
    label: str
    keywords: tuple[str, ...]
    suggested_replies: tuple[str, ...]
    style_hint: str
    follow_up_line: str | None = None


@dataclass(frozen=True)
class IntentAssessment:
    intent: str
    label: str
    confidence: float
    suggested_replies: list[str] = field(default_factory=list)
    style_hint: str = ""
    follow_up_line: str | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None


INTENT_PROFILES: tuple[IntentProfile, ...] = (
    IntentProfile(
        name="admissions_schedule",
        label="Lich thi tuyen sinh",
        keywords=("lich thi", "ngay thi", "bao gio thi", "khi nao thi", "tuyen sinh lop 10"),
        suggested_replies=(
            "Dieu kien du thi la gi?",
            "Ho so can nhung gi?",
            "Cau truc cac mon thi ra sao?",
        ),
        style_hint=(
            "Neu cau hoi ve lich thi, tra loi ro moc thoi gian, tach tung ngay neu co, "
            "va neu thong tin la du kien thi ghi ro la du kien."
        ),
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm điều kiện dự thi hoặc cấu trúc các môn thi.",
    ),
    IntentProfile(
        name="mock_exam_schedule",
        label="Lich thi thu",
        keywords=("thi thu", "thu tuyen sinh", "thu lop 10", "thi thu tuyen sinh"),
        suggested_replies=(
            "Le phi thi thu la bao nhieu?",
            "Dang ky thi thu nhu the nao?",
            "Thi thu co mon nao?",
        ),
        style_hint="Neu cau hoi ve thi thu, tra loi ro lich, cach dang ky, le phi hoac mon thi neu co.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm cách đăng ký hoặc lệ phí thi thử.",
    ),
    IntentProfile(
        name="admissions_eligibility",
        label="Dieu kien du thi",
        keywords=("dieu kien", "doi tuong", "toan quoc", "duoc thi", "du thi", "tot nghiep thcs", "do tuoi"),
        suggested_replies=(
            "Ho so can nhung gi?",
            "Lich thi khi nao?",
            "Dang ky du thi o dau?",
        ),
        style_hint="Neu cau hoi ve dieu kien du thi, tra loi ngan gon theo tung y ro rang.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm hồ sơ cần chuẩn bị hoặc lịch thi.",
    ),
    IntentProfile(
        name="admissions_dossier",
        label="Ho so dang ky",
        keywords=("ho so", "giay to", "hoc ba", "phieu dang ky", "giay khai sinh", "minh chung uu tien"),
        suggested_replies=(
            "Thoi gian dang ky la khi nao?",
            "Dieu kien du thi la gi?",
            "Le phi du thi bao nhieu?",
        ),
        style_hint="Neu cau hoi ve ho so, tra loi theo dang checklist de de doc.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm thời gian đăng ký hoặc lệ phí dự thi.",
    ),
    IntentProfile(
        name="admissions_method",
        label="Phuong thuc tuyen sinh",
        keywords=("phuong thuc", "xet tuyen", "thi tuyen", "cach tuyen sinh"),
        suggested_replies=(
            "Lich thi khi nao?",
            "Dieu kien du thi la gi?",
            "Co duoc dang ky nhieu nguyen vong khong?",
        ),
        style_hint="Neu cau hoi ve phuong thuc tuyen sinh, tra loi ro cach tuyen, mon thi va logic xet tuyen neu co.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm lịch thi hoặc điều kiện dự thi.",
    ),
    IntentProfile(
        name="exam_structure",
        label="Cau truc mon thi",
        keywords=("cau truc mon thi", "cac mon thi", "mon thi nao", "thi gom nhung mon nao", "thi may mon", "mon khong chuyen", "mon chuyen"),
        suggested_replies=(
            "Dieu kien du thi la gi?",
            "Lich thi khi nao?",
            "Co duoc dang ky 2 mon chuyen khong?",
        ),
        style_hint="Neu cau hoi ve cau truc mon thi, tra loi ro so bai thi, ten tung mon va luu y ve mon chuyen.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm điều kiện dự thi hoặc cách tính điểm.",
    ),
    IntentProfile(
        name="tuition_finance",
        label="Hoc phi va chi phi",
        keywords=("hoc phi", "hoc phi", "le phi", "chi phi", "hoc bong", "phi"),
        suggested_replies=(
            "Ho so can nhung gi?",
            "Lich thi khi nao?",
            "Co nhung co so nao?",
        ),
        style_hint="Neu cau hoi ve hoc phi hay le phi, tra loi that than trong, chi noi dung co xac nhan.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm thông tin về hồ sơ hoặc lịch tuyển sinh.",
    ),
    IntentProfile(
        name="campus_facilities",
        label="Co so va dia chi",
        keywords=("co so", "dia chi", "quan 5", "thu duc", "o dau", "di den", "khuon vien"),
        suggested_replies=(
            "Truong co nhung hoat dong ngoai khoa nao?",
            "Thu vien cua truong nhu the nao?",
            "Phuong tien di den truong ra sao?",
        ),
        style_hint="Neu cau hoi ve co so, nen tra loi ro ten co so, dia diem va thong tin lien quan.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm thông tin về thư viện hoặc phương tiện đến trường.",
    ),
    IntentProfile(
        name="extracurricular",
        label="Ngoai khoa va CLB",
        keywords=("ngoai khoa", "clb", "cau lac bo", "su kien", "ignicia", "1000days", "hoa phuong do", "hoi trai", "festival", "doan truong", "ban chap hanh", "bch", "doan hoi"),
        suggested_replies=(
            "Truong co nhung CLB hoc thuat nao?",
            "Doi song hoc sinh PTNK co gi noi bat?",
            "Co nhung su kien lon nao trong nam?",
        ),
        style_hint="Neu cau hoi ve ngoai khoa, nen tra loi sinh dong, neu ten CLB hay su kien noi bat thi liet ke ngan gon.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm các câu lạc bộ hoặc sự kiện nổi bật khác.",
    ),
    IntentProfile(
        name="study_abroad",
        label="Du hoc va hoc bong",
        keywords=(
            "du hoc",
            "hoc bong",
            "ivy league",
            "du hoc my",
            "du hoc uc",
            "du hoc singapore",
            "song ngu",
            "ho so du hoc",
            "hop tac quoc te",
            "phong hop tac quoc te",
            "international office",
        ),
        suggested_replies=(
            "Truong ho tro ho so du hoc nhu the nao?",
            "Co giay to song ngu khong?",
            "Doi song hoc sinh PTNK co gi noi bat?",
        ),
        style_hint="Neu cau hoi ve du hoc, tra loi ro diem manh, lo trinh ho tro va cac loai giay to neu co.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm thông tin về hỗ trợ hồ sơ hoặc giấy tờ song ngữ.",
    ),
    IntentProfile(
        name="library_services",
        label="Thu vien",
        keywords=("thu vien", "library", "muon sach", "khong gian hoc", "phong doc"),
        suggested_replies=(
            "Co so Quan 5 o dau?",
            "Truong co nhung hoat dong ngoai khoa nao?",
            "Phuong tien di den truong ra sao?",
        ),
        style_hint="Neu cau hoi ve thu vien, tra loi ro dich vu, khong gian va cach su dung neu co.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm thông tin về cơ sở hoặc hoạt động học sinh.",
    ),
    IntentProfile(
        name="transport",
        label="Di chuyen",
        keywords=("xe buyt", "di lai", "di chuyen", "transport", "gui xe", "duong den truong"),
        suggested_replies=(
            "Co so Thu Duc o dau?",
            "Co so Quan 5 o dau?",
            "Thu vien cua truong nhu the nao?",
        ),
        style_hint="Neu cau hoi ve di chuyen, tra loi ro cach den truong, dia diem va luu y thuc te neu co.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm địa chỉ cơ sở hoặc thông tin học tập tại trường.",
    ),
    IntentProfile(
        name="exam_review",
        label="Cam nhan de thi",
        keywords=("de thi", "cam nhan", "phong van", "sau ky thi", "de van", "de toan", "de chuyen"),
        suggested_replies=(
            "Lich thi tuyen sinh la khi nao?",
            "Phuong thuc tuyen sinh ra sao?",
            "Dieu kien du thi la gi?",
        ),
        style_hint="Neu cau hoi ve de thi hay cam nhan sau thi, tra loi tom tat y kien noi bat mot cach trung lap.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm lịch thi hoặc phương thức tuyển sinh.",
    ),
    IntentProfile(
        name="contact",
        label="Lien he",
        keywords=("lien he", "hotline", "email", "facebook", "fanpage", "website"),
        suggested_replies=(
            "Lich thi tuyen sinh la khi nao?",
            "Ho so can nhung gi?",
            "Co so Quan 5 o dau?",
        ),
        style_hint="Neu cau hoi ve lien he, tra loi ro tung kenh mot.",
        follow_up_line="Nếu bạn muốn, mình có thể hỗ trợ thêm về lịch thi, hồ sơ hoặc thông tin cơ sở.",
    ),
    IntentProfile(
        name="general_admissions",
        label="Tu van tuyen sinh chung",
        keywords=("tuyen sinh", "lop 10", "ts 10", "thong tin ts 10", "nguyen vong", "chi tieu", "thi vao ptnk"),
        suggested_replies=(
            "Lich thi tuyen sinh la khi nao?",
            "Dieu kien du thi la gi?",
            "Ho so can nhung gi?",
        ),
        style_hint="Neu cau hoi chung ve tuyen sinh, tra loi tong quan ngan gon va chi giu cac thong tin lien quan truc tiep den cau hoi hien tai.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm lịch thi, điều kiện dự thi hoặc hồ sơ cần chuẩn bị.",
    ),
    IntentProfile(
        name="school_life",
        label="Doi song hoc sinh",
        keywords=("doi song", "hoc sinh", "moi truong", "co ap luc khong", "co vui khong", "trai nghiem"),
        suggested_replies=(
            "Truong co nhung hoat dong ngoai khoa nao?",
            "PTNK co ho tro du hoc khong?",
            "Co nhung co so nao?",
        ),
        style_hint="Neu cau hoi ve doi song hoc sinh, tra loi tu nhien, tap trung vao trai nghiem hoc tap va hoat dong.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm về hoạt động ngoại khóa hoặc cơ hội du học.",
    ),
    IntentProfile(
        name="research_science",
        label="Nghien cuu khoa hoc",
        keywords=("nghien cuu khoa hoc", "nghien cuu", "nckh", "khoa hoc", "stem", "pris", "du an nghien cuu", "lien nganh"),
        suggested_replies=(
            "PTNK co chuong trinh lien nganh nao?",
            "Co CLB STEM khong?",
            "Hoc sinh co duoc mentor nghien cuu khong?",
        ),
        style_hint="Neu cau hoi ve nghien cuu khoa hoc, tra loi ro co hoi tham gia, CLB hoac chuong trinh lien quan.",
        follow_up_line="Nếu bạn muốn, mình có thể gửi thêm về chương trình liên ngành hoặc các hoạt động STEM.",
    ),
    IntentProfile(
        name="general_support",
        label="Tu van chung",
        keywords=(),
        suggested_replies=(
            "Lich thi tuyen sinh la khi nao?",
            "Dieu kien du thi la gi?",
            "Ho so can nhung gi?",
        ),
        style_hint="Tra loi tu nhien, ngan gon, di thang vao cau hoi hien tai va khong mo rong sang chu de khac neu nguoi dung chua hoi.",
        follow_up_line="Nếu bạn muốn, mình có thể hỗ trợ thêm về lịch thi, điều kiện dự thi hoặc hồ sơ.",
    ),
)


class PTNKChatAdvisor:
    def assess(self, message: str, history: list[ChatTurn] | None = None) -> IntentAssessment:
        normalized_message = self._normalize(message)
        recent_user_turns = self._build_recent_user_turns(history or [])
        normalized_history = " ".join(recent_user_turns).strip()
        normalized_context = " ".join(part for part in (normalized_message, normalized_history) if part).strip()

        clarification = self._detect_clarification(normalized_message, normalized_context)
        if clarification is not None:
            return clarification

        specific_profiles = [
            profile
            for profile in INTENT_PROFILES
            if profile.name not in {"general_admissions", "general_support"}
        ]
        general_admissions_profile = next(
            profile for profile in INTENT_PROFILES if profile.name == "general_admissions"
        )
        general_support_profile = INTENT_PROFILES[-1]

        best_profile, best_score = self._pick_best_profile(
            specific_profiles,
            normalized_message,
        )
        confidence = self._confidence_from_score(best_score)

        if best_score > 0:
            return IntentAssessment(
                intent=best_profile.name,
                label=best_profile.label,
                confidence=confidence,
                suggested_replies=list(best_profile.suggested_replies),
                style_hint=best_profile.style_hint,
                follow_up_line=best_profile.follow_up_line,
            )

        general_admissions_score = self._score_keywords(general_admissions_profile, normalized_message)
        if general_admissions_score > 0:
            return IntentAssessment(
                intent=general_admissions_profile.name,
                label=general_admissions_profile.label,
                confidence=self._confidence_from_score(general_admissions_score),
                suggested_replies=list(general_admissions_profile.suggested_replies),
                style_hint=general_admissions_profile.style_hint,
                follow_up_line=general_admissions_profile.follow_up_line,
            )

        best_profile, best_score = self._pick_best_profile_from_recent_history(
            specific_profiles,
            recent_user_turns,
        )
        if best_score > 0:
            return IntentAssessment(
                intent=best_profile.name,
                label=best_profile.label,
                confidence=0.6 if best_score >= 0.65 else 0.5,
                suggested_replies=list(best_profile.suggested_replies),
                style_hint=best_profile.style_hint,
                follow_up_line=best_profile.follow_up_line,
            )

        history_general_score = self._score_recent_history(general_admissions_profile, recent_user_turns)
        if history_general_score > 0:
            return IntentAssessment(
                intent=general_admissions_profile.name,
                label=general_admissions_profile.label,
                confidence=0.5,
                suggested_replies=list(general_admissions_profile.suggested_replies),
                style_hint=general_admissions_profile.style_hint,
                follow_up_line=general_admissions_profile.follow_up_line,
            )

        return IntentAssessment(
            intent=general_support_profile.name,
            label=general_support_profile.label,
            confidence=0.35,
            suggested_replies=list(general_support_profile.suggested_replies),
            style_hint=general_support_profile.style_hint,
            follow_up_line=general_support_profile.follow_up_line,
        )

    def _detect_clarification(
        self,
        normalized_message: str,
        normalized_context: str,
    ) -> IntentAssessment | None:
        has_schedule = any(keyword in normalized_message for keyword in ("lich thi", "ngay thi", "bao gio thi", "khi nao thi"))
        if has_schedule:
            has_admissions = any(keyword in normalized_context for keyword in ("tuyen sinh", "lop 10", "mon chuyen", "du thi"))
            has_mock = any(keyword in normalized_context for keyword in ("thi thu", "thu tuyen sinh"))
            has_interview = any(keyword in normalized_context for keyword in ("phong van", "cam nhan de thi", "sau ky thi"))
            categories = sum([has_admissions, has_mock, has_interview])
            if categories == 0:
                return IntentAssessment(
                    intent="clarify_schedule",
                    label="Lam ro lich thi",
                    confidence=0.99,
                    suggested_replies=[
                        "Lich thi tuyen sinh lop 10",
                        "Lich thi thu tuyen sinh",
                        "Thong tin phong van sau ky thi",
                    ],
                    needs_clarification=True,
                    clarification_question=(
                        "Chào bạn,\n\n"
                        "Bạn đang hỏi lịch thi tuyển sinh lớp 10, lịch thi thử hay thông tin phỏng vấn sau kỳ thi?"
                    ),
                )

        has_registration = any(keyword in normalized_message for keyword in ("dang ky", "nop ho so", "nop don"))
        if has_registration and "tuyen sinh" not in normalized_context and "clb" not in normalized_context and "ngoai khoa" not in normalized_context:
            return IntentAssessment(
                intent="clarify_registration",
                label="Lam ro dang ky",
                confidence=0.95,
                suggested_replies=[
                    "Dang ky tuyen sinh lop 10",
                    "Dang ky thi thu tuyen sinh",
                    "Dang ky hoat dong ngoai khoa",
                ],
                needs_clarification=True,
                clarification_question=(
                    "Chào bạn,\n\n"
                    "Bạn đang hỏi đăng ký tuyển sinh lớp 10, đăng ký thi thử hay đăng ký hoạt động/câu lạc bộ?"
                ),
            )

        return None

    def _score_intent(self, profile: IntentProfile, normalized_message: str, normalized_history: str) -> float:
        score = 0.0
        for keyword in profile.keywords:
            if keyword in normalized_message:
                score += 2.0
            elif keyword in normalized_history:
                score += 0.35
        return score

    def _pick_best_profile(
        self,
        profiles: list[IntentProfile],
        normalized_message: str,
    ) -> tuple[IntentProfile, float]:
        best_profile = profiles[0]
        best_score = 0.0
        for profile in profiles:
            score = self._score_keywords(profile, normalized_message)
            if score > best_score:
                best_profile = profile
                best_score = score
        return best_profile, best_score

    def _pick_best_profile_from_recent_history(
        self,
        profiles: list[IntentProfile],
        recent_user_turns: list[str],
    ) -> tuple[IntentProfile, float]:
        best_profile = profiles[0]
        best_score = 0.0
        for profile in profiles:
            score = self._score_recent_history(profile, recent_user_turns)
            if score > best_score:
                best_profile = profile
                best_score = score
        return best_profile, best_score

    def _score_keywords(self, profile: IntentProfile, normalized_text: str) -> float:
        score = 0.0
        for keyword in profile.keywords:
            if keyword in normalized_text:
                score += 2.0
        return score

    def _score_recent_history(self, profile: IntentProfile, recent_user_turns: list[str]) -> float:
        if not recent_user_turns:
            return 0.0

        score = 0.0
        recency_weights = (0.8, 0.45, 0.25)
        for index, turn in enumerate(reversed(recent_user_turns[-3:])):
            weight = recency_weights[index] if index < len(recency_weights) else 0.15
            for keyword in profile.keywords:
                if keyword in turn:
                    score += weight
        return score

    def _build_recent_user_turns(self, history: list[ChatTurn]) -> list[str]:
        return [
            self._normalize(turn.content)
            for turn in history[-4:]
            if turn.role == "user" and turn.content.strip()
        ]

    @staticmethod
    def _confidence_from_score(score: float) -> float:
        if score >= 3:
            return 0.95
        if score >= 2:
            return 0.8
        if score >= 1:
            return 0.65
        return 0.35

    def _normalize(self, text: str) -> str:
        text = text.replace("đ", "d").replace("Đ", "D")
        normalized = unicodedata.normalize("NFD", text.lower())
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return " ".join(normalized.split())
