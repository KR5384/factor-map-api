"""リクエストの形と入力チェック（API仕様書の「リクエストボディ」「入力チェック」）。

数値は strict（"3" や true を数値として受け付けない）。仕様にない項目は無視する。
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StrictBool, StringConstraints, create_model, field_validator

from app.scoring import QUESTION_KEYS

Scale5 = Annotated[int, Field(strict=True, ge=1, le=5)]
Scale4 = Annotated[int, Field(strict=True, ge=1, le=4)]
Version = Annotated[str, StringConstraints(min_length=1, max_length=32)]
DiagnosisId = Annotated[str, StringConstraints(min_length=1, max_length=64)]

CAUSE_NONE = 98
CAUSE_UNKNOWN = 99
ALLOWED_CAUSES = set(range(1, 11)) | {CAUSE_NONE, CAUSE_UNKNOWN}


class PreSurveyIn(BaseModel):
    consent: StrictBool
    consent_version: Version
    client_version: Version
    pre_frequency: Scale4
    pre_explain: Scale5
    pre_relation: Scale5
    pre_causes: Annotated[list[Annotated[int, Field(strict=True)]], Field(min_length=1, max_length=11)]
    age_group: Literal["20s", "30s", "40s", "50plus", "no_answer"] | None = None

    @field_validator("consent")
    @classmethod
    def must_consent(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("利用同意が必要です")
        return v

    @field_validator("pre_causes")
    @classmethod
    def check_causes(cls, v: list[int]) -> list[int]:
        bad = [x for x in v if x not in ALLOWED_CAUSES]
        if bad:
            raise ValueError(f"使えない値があります: {bad}")
        if len(set(v)) != len(v):
            raise ValueError("同じ値が重複しています")
        if {CAUSE_NONE, CAUSE_UNKNOWN} & set(v) and len(v) > 1:
            raise ValueError("98・99 はほかの値と同時に選べません")
        return v


Answers = create_model("Answers", **{q: (Scale5, ...) for q in QUESTION_KEYS})


class FactorAnalysisIn(BaseModel):
    diagnosis_id: DiagnosisId
    answers: Answers


class PostSurveyIn(BaseModel):
    diagnosis_id: DiagnosisId
    post_explain: Scale5
    post_relation: Scale5
    post_fit: Scale5 | None = None
    post_discovery: Scale5 | None = None
    post_comment: str | None = None

    @field_validator("post_comment")
    @classmethod
    def clean_comment(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if len(v) > 200:
            raise ValueError("感想は200文字までです")
        return v or None
