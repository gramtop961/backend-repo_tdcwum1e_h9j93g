"""
Database Schemas for NoteBuddy

Each Pydantic model below represents one MongoDB collection. The collection
name is the lowercase of the class name, e.g., Note -> "note".

Collections:
- Note: accepted/published notes metadata stored with Google Drive link
- Upload: incoming submissions pending review by admin
- Contributor: people who contribute notes and earn Knowledge Points
- Settings: site-wide settings (hero text, featured, language)
- Subject: controlled list of subjects
- College: controlled list of colleges

These models are used for validation when creating/editing documents.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl


class Note(BaseModel):
    title: str = Field(..., description="Note title")
    class_level: str = Field(..., description="Class level e.g., 11, 12, Other")
    college: str = Field(..., description="College name e.g., LBA, Other")
    subject: str = Field(..., description="Subject name")
    chapters: List[str] = Field(default_factory=list, description="Chapters/tags")
    pages: Optional[int] = Field(None, ge=1, description="Estimated number of pages")
    drive_link: HttpUrl = Field(..., description="Google Drive view-only link")
    uploader_alias: str = Field("Admin Upload", description="Display name of uploader")
    contributor_id: Optional[str] = Field(None, description="Linked contributor id if any")
    thumbnail_url: Optional[HttpUrl] = Field(None, description="Optional preview image URL")
    likes: int = Field(0, ge=0)
    downloads: int = Field(0, ge=0)
    language: str = Field("en", description="en or ne")


class Upload(BaseModel):
    title: str
    class_level: str
    college: str
    subject: str
    chapters: List[str] = []
    pages: Optional[int] = None
    drive_link: HttpUrl
    contributor_name: Optional[str] = None
    notes: Optional[str] = Field(None, description="Contributor note")
    thumbnail_url: Optional[HttpUrl] = None
    status: str = Field("pending", description="pending|accepted|rejected")
    reviewer_note: Optional[str] = None
    suggested_points: Optional[int] = None
    assigned_points: Optional[int] = None


class Contributor(BaseModel):
    name: str
    email: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None
    college: Optional[str] = None
    points: int = Field(0, ge=0)
    streak: int = Field(0, ge=0)
    badges: List[str] = Field(default_factory=list)


class Settings(BaseModel):
    hero_title_en: str = Field("Share & Discover premium notes", description="Hero title EN")
    hero_title_ne: str = Field("नोटहरू सेयर र खोज्नुहोस्", description="Hero title NE")
    language_default: str = Field("en", description="en or ne")
    featured_contributor_ids: List[str] = Field(default_factory=list)
    google_drive_folder_id: Optional[str] = None
    seo_meta_description: Optional[str] = None


class Subject(BaseModel):
    name: str
    slug: str
    stream: Optional[str] = Field(None, description="Science/Management/Law/Languages")


class College(BaseModel):
    name: str
    code: Optional[str] = None
