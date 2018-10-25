from sqlalchemy import Column, ForeignKey, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import DateTime

Base = declarative_base()
 
class User(Base):
    __tablename__ = 'users'
    user_id = Column(String, primary_key=True)
    user_name = Column(String, nullable=False)
    link_karma = Column(String, nullable=True)
    comment_karma = Column(String, nullable=True)
 
class Post(Base):
    __tablename__ = 'posts'
    post_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.user_id'))
    sub_id = Column(String, ForeignKey('subreddits.sub_id'))
    title = Column(String)
    created = Column(DateTime)
    score = Column(Integer)
    body = Column(String)
    num_comments = Column(Integer)
    is_self = Column(Boolean)
    target_url = Column(String)
    permalink = Column(String)

class Comment(Base):
    __tablename__ = 'comments'
    comment_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.user_id'))
    post_id = Column(String, ForeignKey('posts.post_id'))
    created = Column(DateTime)
    score = Column(Integer)
    gilds = Column(Integer)
    body = Column(String)
    permalink = Column(String)

    #person = relationship(Person)

class Subreddit(Base):
    __tablename__ = 'subreddits'
    sub_id = Column(String, primary_key=True)
    sub_name = Column(String, nullable=False)
    description = Column(String)
    public_description = Column(String)
    created = Column(DateTime)
    sub_count = Column(Integer)
    audience = Column(String)
    url = Column(String)
