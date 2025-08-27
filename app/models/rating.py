from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database.base import Base

class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, index=True)
    trip_id = Column(String, ForeignKey("trips.id"), nullable=False)
    rater_id = Column(String, ForeignKey("users.id"), nullable=False)
    rated_id = Column(String, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(String, nullable=True)
    punctuality = Column(Integer, nullable=True)
    cleanliness = Column(Integer, nullable=True)
    communication = Column(Integer, nullable=True)
    safety = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rater = relationship("User", foreign_keys=[rater_id])
    rated = relationship("User", foreign_keys=[rated_id])
    trip = relationship("Trip")


