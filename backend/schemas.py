from typing import List, Optional
from pydantic import BaseModel, HttpUrl, Field


class Subject(BaseModel):
    id: Optional[str] = None
    name: str
    stream: Optional[str] = None  # Science/Management/Law/Languages


class College(BaseModel):
    id: Optional[str] = None
    name: str
    code: Optional[str] = None


class Note(BaseModel):
    id: Optional[str] = None
    title: str
    subject: str
    class_level: str
    college: str
    tags: List[str] = []
    pages: Optional[int] = None
    drive_link: HttpUrl
    thumbnail: Optional[HttpUrl] = None
    downloads: int = 0
    likes: int = 0


class Upload(BaseModel):
    id: Optional[str] = None
    title: str
    subject: str
    class_level: str
    college: str
    tags: List[str] = []
    pages: Optional[int] = None
    drive_link: HttpUrl
    contributor_name: Optional[str] = None
    status: str = Field(default="pending")  # pending/accepted/rejected
    reviewer_note: Optional[str] = None


class Contributor(BaseModel):
    id: Optional[str] = None
    name: str
    points: int = 0
    avatar: Optional[str] = None


class Settings(BaseModel):
    id: Optional[str] = None
    hero_title: str = "NoteBuddy — Share & Discover"
    hero_subtitle: str = "Curated notes for Class 11 & 12"
    featured_contributors: List[str] = []  # list of contributor ids or names
    default_language: str = "en"
    meta_description: str = "Premium notes for Nepal +2 students"
