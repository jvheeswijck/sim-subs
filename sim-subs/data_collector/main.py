#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
{Description}
{License_info}
'''




import argparse
import datetime as dt
import json
import logging
import time

import praw
from sqlalchemy import create_engine
from sqlalchemy import exists
from sqlalchemy.orm import sessionmaker

from sqlalchemy_declarative import User, Comment, Post, Subreddit, Base

# File Settings
reddit_auth_file = 'reddit_auth.txt'
db_settings_file = 'db_settings.txt'
sub_list_file = 'subs.txt'
sub_history_file = ''

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='Retrieve posts and comments from Reddit and store in a database.')
parser.add_argument('--comment_limit')
parser.add_argument('--post_limit')
parser.add_argument('--post_file')  # Not yet implemented
parser.add_argument('--oldest_first')  # Not yet implemented
parser.add_argument('--verbose')


def init_sessions():
    """
    Initializes a PRAW Reddit instance and a DB session with their respective credentials
    
    Returns
    -------
    A tuple with the Reddit instance and DB session

    """
    # Load Authentication Details
    with open(reddit_auth_file, 'r') as f:
        auth = json.load(f)

    with open(db_settings_file, 'r') as f:
        db_settings = json.load(f)

    usr_agnt = 'python:front_page_praw:v0.2 (by /u/c_nor)'
    reddit = praw.Reddit(client_id=auth['client_id'],
                         client_secret=auth['client_secret'],
                         user_agent=usr_agnt)

    # Create Postgres Connection
    engine_address = 'postgresql://{user}:{password}@{address}/{db_name}'.format(
        user=db_settings['user'],
        password=db_settings['password'],
        address=db_settings['address'],
        db_name=db_settings['db_name']

    )
    cnx = create_engine(engine_address)
    Base.metadata.bind = cnx
    dbsession = sessionmaker(bind=cnx)
    return reddit, dbsession()


def store_posts(posts, session, comment_limit=100, more_comments=0, threshold=0, verbose=True):
    """ Takes a list of PRAW Submissions and stores the post and a comments in a database
    
    Parameters
    ----------
    posts : list
        A list containing PRAW Submission objects
    session : sqlalchemy.orm.session.Session
        A SQL Alchemy session
    comment_limit : int
        Maximum number of comments retrieved per post
    more_comments : int
        Maximum number of 'More Comments' requests performed by PRAW
    threshold : int
        Minimum number of comments in 'More Comments" required for a request
    verbose : boolean
        Whether more info will be displayed in the console.

    Returns
    -------
    None

    """

    posts_completed = 0
    st_time = time.time()

    for i, post in enumerate(posts):

        # Check if post already exists in database
        post_id = post.fullname
        post_exist = session.query(exists().where(Post.post_id == post_id)).scalar()

        if not post_exist:
            if verbose:
                print('Retrieving {0} at {1}. Current step {2} / {3}'.format(
                    post_id,
                    time.strftime('%H:%M'), i + 1,
                    len(posts)))
                print('Elapsed time {}'.format(time.time() - st_time))
                print('Posts completed {}'.format(posts_completed))

            new_post = create_post(post)

            logging.debug('Checking existence of subreddit')
            # Check if the submission's subreddit is already in the database otherwise insert it
            sub_exists = session.query(exists().where(Subreddit.sub_id == new_post.sub_id)).scalar()
            if not sub_exists:
                session.add(create_subreddit(post.subreddit))
                session.commit()

            logging.debug('Checking existence of post author')
            # Check if the submission's author is already in the database otherwise insert it
            user_exists = session.query(exists().where(User.user_id == new_post.user_id)).scalar()
            if not user_exists:
                session.add(create_user(post))
                session.commit()

            session.add(new_post)
            session.commit()

            # Get comments from the submission
            logging.debug('Getting comment list')
            post.comments.replace_more(limit=more_comments, threshold=threshold)
            comment_list = post.comments.list()
            comment_total = len(comment_list)
            if comment_total > comment_limit:
                comment_list = comment_list[:comment_limit]
                comment_total = len(comment_list)

            # Check which comment authors are already in the database
            logger.debug('Querying DB for existing users')
            post_user_list = set()
            for comment in comment_list:
                try:
                    post_user_list.add(comment.author_fullname)
                except:
                    continue
            existing_ids = [x.user_id for x in session.query(User).filter(User.user_id.in_(post_user_list)).all()]

            # Insert new users into database
            logger.debug('Creating new users')
            users_added = []
            for comment in comment_list:
                try:
                    user_id = comment.author_fullname
                    if not (user_id in existing_ids) and not (user_id in users_added):
                        users_added.append(user_id)
                        session.add(create_user(comment))
                except:
                    continue
            session.commit()

            # Store comments into database
            logger.debug('Storing comments')
            for j, comment in enumerate(comment_list):
                logger.debug('Storing comment {0} out of {1}'.format(j, comment_total))
                session.add(create_comment(comment, new_post))
            session.commit()
            posts_completed += 1
        else:
            if verbose:
                print('Post {} already exists'.format(post_id))


def create_user(e, store_karma=False):
    """
    Creates a User instance for SQL Alchemy
    Parameters
    ----------
    e : PRAW Redditor, Comment or Post object
    store_karma : bool
        Whether the user's karma will be stored. Recommended to leave false
        as enabling this will slow down the script considerably.

    Returns
    -------
    User instance object

    Notes
    -----
    (See SqlAlchemy_declarative.py)
    """
    new_user = None
    if store_karma:
        if type(e) == praw.models.reddit.redditor.Redditor:
            new_user = User(user_id=e.author.fullname)
            new_user.user_name = e.author.name
            new_user.link_karma = e.author.link_karma
            new_user.comment_karma = e.author.comment_karma
    else:
        new_user = User(user_id=e.author_fullname)
        new_user.user_name = e.author.name
        new_user.link_karma = None
        new_user.comment_karma = None
    return new_user


def create_subreddit(sub):
    """
    Constructs an instance of the SQL base class Subreddit to insert into the subreddit table.
    
    Parameters
    ----------
    sub : PRAW Subreddit instance

    Returns
    -------
    Subreddit instance object (SQLAlchemy)
    """
    new_sub = Subreddit(sub_id=sub.fullname)
    new_sub.sub_name = sub.display_name
    new_sub.created = dt.datetime.fromtimestamp(sub.created_utc)
    new_sub.description = sub.description
    new_sub.sub_count = sub.subscribers
    new_sub.audience = sub.audience_target
    new_sub.url = sub.url

    return new_sub


def create_post(post):
    """
    Constructs an instance of the SQL base class Subreddit to insert into the subreddit table.
    
    Parameters
    ----------
    post : PRAW Submission object

    Returns
    -------
    Post class object (SQL Alchemy)

    """
    new_post = Post(post_id=post.fullname)

    try:
        new_post.user_id = post.author_fullname
    except:
        new_post.user_id = 't2_nan'

    new_post.sub_id = post.subreddit.fullname
    new_post.title = post.title
    new_post.created = dt.datetime.fromtimestamp(post.created_utc)
    new_post.score = post.score
    new_post.target_url = post.url
    new_post.permalink = post.permalink
    new_post.body = post.selftext
    new_post.num_comments = post.num_comments
    new_post.is_self = False if post.is_self == 'False' else True
    return new_post


def create_comment(comment, post):
    """
    Constructs an instance of the SQL base class Subreddit to insert into the subreddit table.

    Parameters
    ----------
    comment : PRAW Comment object
    post : PRAW Post object

    Returns
    -------

    """
    new_comment = Comment(comment_id=comment.fullname)
    try:
        new_comment.user_id = comment.author_fullname
    except:
        new_comment.user_id = 't2_nan'

    new_comment.post_id = post.post_id
    new_comment.created = dt.datetime.fromtimestamp(comment.created_utc)
    new_comment.score = comment.score
    new_comment.gilds = comment.gilded
    new_comment.body = comment.body
    new_comment.permalink = comment.permalink
    return new_comment


def main():
    sub_list = None
    args = parser.parse_args()
    reddit, db_session = init_sessions()

    comment_limit = int(args.comment_limit) if args.comment_limit else 40
    post_limit = int(args.post_limit) if args.post_limit else 15
    is_verbose = True if args.verbose == 'True' else False

    if args.post_file:
        pass

    if args.oldest_first:
        pass
    else:
        try:
            with open(sub_list_file, 'r') as f:
                sub_list = map(str.strip, f.readlines())
        except OSError:
            sub_list = None
            print('No posts or subs were found. Please create a file with a list of sub names or specify the location'
                  ' of such a file above.')
            exit()

    script_st_time = time.time()
    print('Script started at ', time.strftime('%H:%M'))

    if sub_list is not None:
        for display_name in sub_list:
            praw_subreddit = reddit.subreddit(display_name)
            print('--------------------------------------')
            print('Current subreddit: {}'.format(praw_subreddit.display_name))
            sub_st_time = time.time()
            post_list = list(praw_subreddit.hot(limit=post_limit))
            store_posts(post_list, db_session, comment_limit, verbose=is_verbose)
            print('Subreddit completed in ', round(time.time() - sub_st_time, 2), ' seconds.')
    print('Script finished at ', time.strftime('%H:%M'))
    print('Time taken: ', round((script_st_time - time.time()) / 60, 2), ' minutes.')


if __name__ == '__main__':
    main()
