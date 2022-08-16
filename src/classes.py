from enum import Enum
from pydantic import BaseModel

class Draft(BaseModel):
    title: str = ""
    article_text: str = ""

class Review(BaseModel):
    review_text : str = ""

class Select_role(str, Enum):
    moderator = "moderator"
    writer = "writer"
    ban = "ban"

class Action_role(str, Enum):
    add = "add"
    remove = "remove"

class Select_rate(str, Enum):
    one = "1"
    two = "2"
    three = "3"
    four = "4"
    five = "5"
    grater_than_two = ">2"
    grater_than_three = ">3"
    grater_than_four = ">4"
    less_than_two = "<2"
    less_than_three = "<3"
    less_than_four = "<4"

class Select_search_field(str, Enum):
    name = "name"
    author = "author"
    topic = "topic"
    date = "date"

class Select_topic(str, Enum):
    science = "science"
    art = "art"
    history = "history"
    news = "news"