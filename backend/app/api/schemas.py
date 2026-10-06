import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class OrganizationIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    domains: list[str] = Field(default_factory=list, max_length=30)
    reference_ids: list[str] = Field(default_factory=list, max_length=30)
    importance: Literal["normal", "critical"] = "normal"

    @field_validator("aliases", "reference_ids")
    @classmethod
    def terms(cls, value):
        if any(len(v.strip()) < 3 or len(v) > 200 for v in value):
            raise ValueError("Reference values must contain 3–200 characters")
        return [v.strip() for v in value]

    @field_validator("domains")
    @classmethod
    def domain_values(cls, value):
        if any(not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,250})\.[a-zA-Z]{2,63}", v) for v in value):
            raise ValueError("Enter exact domain names without a URL, path, or wildcard")
        return [v.lower() for v in value]


class SourceConfig(BaseModel):
    model_config = {"extra": "forbid"}
    url: str | None = Field(default=None, max_length=2000)
    path: str | None = Field(default=None, max_length=2000)
    allowed_hosts: list[str] = Field(default_factory=list, max_length=10)
    path_prefixes: list[str] = Field(default_factory=list, max_length=10)
    max_depth: int = Field(default=1, ge=0, le=3)
    max_documents: int = Field(default=100, ge=1, le=100)
    history_commits: int = Field(default=5, ge=1, le=20)


class SourceIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    kind: Literal["git", "http"]
    access_context: Literal["authorized_private", "public_observed"] = "authorized_private"
    authorized: bool
    config: SourceConfig

    @model_validator(mode="after")
    def validate_source(self):
        if not self.authorized:
            raise ValueError("Explicit authorization is required")
        if self.kind == "http" and (not self.config.url or self.config.path):
            raise ValueError("HTTP sources require a URL")
        if self.kind == "git" and bool(self.config.url) == bool(self.config.path):
            raise ValueError("Git sources require exactly one local path or HTTPS URL")
        if self.config.url and (not self.config.allowed_hosts or not self.config.path_prefixes):
            raise ValueError("Remote sources require exact allowed hosts and path prefixes")
        if any(not p.startswith("/") or ".." in p or "%" in p for p in self.config.path_prefixes):
            raise ValueError("Path prefixes must be canonical absolute URL paths")
        return self


class SourceUpdate(SourceIn):
    expected_revision: int = Field(ge=1)


class SourceArchiveIn(BaseModel):
    archived: bool
    expected_revision: int = Field(ge=1)


class ReviewIn(BaseModel):
    analysis_revision: int | None = Field(default=None, ge=1)
    action: Literal["confirm", "dismiss", "request_context", "remediate", "reopen", "change_priority"]
    reason: str = Field(min_length=3, max_length=3000)
    priority: Literal["high", "medium", "low"] | None = None

    @model_validator(mode="after")
    def require_priority(self):
        if self.action == "change_priority" and self.priority is None:
            raise ValueError("Choose a priority")
        return self


class InvestigationIn(BaseModel):
    analysis_revision: int | None = Field(default=None, ge=1)
    mode: Literal["offline", "live"] = "offline"


class SourceReanalysisIn(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=1000)


class IncidentReanalysisIn(BaseModel):
    source_id: str
    expected_analysis_revision: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=1000)
