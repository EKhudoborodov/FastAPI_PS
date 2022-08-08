import requests, psycopg2, cv2, datetime
import flask

conn = psycopg2.connect(database="server_db",
                        user="postgres",
                        password="postgres",
                        host="localhost",
                        port="5432")

cursor = conn.cursor()

#FOR SIGN IN AND SIGN UP
def stop_sessions():
    flask.session['user'] = None # session for user_id
    flask.session['fullname'] = None # session for user's fullname
    flask.session['role'] = None # session for user's roles
    flask.session['ban'] = None # session for user's ban status
    flask.session['article'] = None # session for name of latest openned article
    flask.session['article_id'] = None # session for id of latest openned article
    flask.session['title'] = None # session for title of latest oppend article
    return 0

def crypt_role(role):
    if role=='writer':
        role_id = 3
    elif role=='moderator':
        role_id = 2
    else:
        role_id = 5
    return role_id
    
def send_roles(records):
    roles = []
    for pair in records:
        roles.append(pair[1])
    return roles

def update_reviews(article_name, user_id, article_id, review, path):
    with open(path, "r") as file:
        lines = file.readlines()
    file.close()
    new_lines = []
    formed_id = str(user_id)
    for line in lines:
        wrong = 1
        for i in range(len(formed_id)):
            if line[i] == formed_id[i]:
                wrong = 0
            else:
                wrong = 1
                break
        if wrong == 0:
            new_lines += f"{user_id}:{review}\n"
        else:
            new_lines += line
    text = form_article(new_lines)
    with open(path, "w") as file:
        file.write(text)
    file.close()
    return 0
    
    

#CHECK
def authorization_check(validate_role, direction):
    ban = flask.session.get('ban')
    user_roles = flask.session.get('role')
    if user_roles == None:
        return flask.redirect(flask.url_for('.sign_in_start'))
    elif user_roles[0] == 1 or user_roles[validate_role] == 1 or direction == 'home':
        #a - admin, m - moder, w - writer, r - reader;
        new_publish = f"({check_writer_uploads()})"
        return flask.render_template(f"{direction}.html", a = user_roles[0], m = user_roles[1], w = user_roles[2], ban = ban, new_publish=new_publish)
    else:
        return flask.redirect(flask.url_for('.home'))

def authorization_editors_check(article_id):
    ban = flask.session.get('ban')
    user_roles = flask.session.get('role')
    if user_roles == None:
        return flask.redirect(flask.url_for('.sign_in_start'))
    else:
        user = flask.session.get('user')
        cursor.execute(f"SELECT * FROM public.article_writer WHERE user_id={user} and article_id={article_id}")
        records = list(cursor.fetchall())
        if user_roles[0] == 1 or (user_roles[1] == 1 and records[0][2] == True):
            #a - admin, m - moder, w - writer, r - reader;
            new_publish = f"({check_writer_uploads()})"
            return flask.render_template("editors.html", a = user_roles[0], m = user_roles[1], w = user_roles[2], ban = ban, new_publish=new_publish)
        else:
            return flask.redirect(flask.url_for('.home'))

def authorization_check_published(article_name):
    ban = flask.session.get('ban')
    user_roles = flask.session.get('role')
    if user_roles == None:
        return flask.redirect(flask.url_for('.sign_in_start'))
    elif user_roles[0] == 1 or user_roles[1] == 1:
        #a - admin, m - moder, w - writer, r - reader;
        new_publish = f"({check_writer_uploads()})"
        cursor.execute(f"SELECT * FROM public.article WHERE name='{article_name}' and isdeleted = {False}")
        records = list(cursor.fetchall())
        if records == []:
            return flask.render_template("a_published.html", a = user_roles[0], m = user_roles[1], w = user_roles[2], ban = ban, new_publish=new_publish, no_article=1)
        else:
            article_id = records[0][0]
            title = records[0][2]
            cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={article_id}")
            check = list(cursor.fetchall())
            path = f".\\articles\\{article_name}.txt"
            text = form_text(path)
            if check[0][1] == 2:
                return flask.render_template("a_published.html", a = user_roles[0], m = user_roles[1], w = user_roles[2], ban = ban, new_publish=new_publish, text=text, title=title)
            elif check[0][1] == 3:    
                return flask.render_template("a_published.html", a = user_roles[0], m = user_roles[1], w = user_roles[2], ban = ban, new_publish=new_publish, text=text, title=title, aprooved=1)
            elif check[0][1] == 4:
                return flask.render_template("a_published.html", a = user_roles[0], m = user_roles[1], w = user_roles[2], ban = ban, new_publish=new_publish, text=text, title=title, denied=1)    
    else:
        return flask.redirect(flask.url_for('.home'))

def authorization_check_draft(article):
    roles = flask.session.get('role')
    ban = flask.session.get('ban')
    if roles == None:
        return flask.redirect(flask.url_for('.sign_in_start'))
    elif roles[0] == 1 or roles[2] == 1:
        cursor.execute(f"SELECT * FROM public.article WHERE name='{article}'")
        records = list(cursor.fetchall())
        if records == []:
            return flask.render_template('draft.html', no_article = 1)
        else:
            title = records[0][2]
            reason = records[0][3]
            cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={records[0][0]} and user_id={flask.session.get('user')}")
            recs = list(cursor.fetchall())
            if recs == []:
                return flask.redirect(flask.url_for('.workshop'))
            author = is_author(records[0][0], flask.session.get('user'))
            path = f".\\articles\\{article}.txt"
            text = form_text(path)
            new_publish = f"({check_writer_uploads()})"
            cursor.execute(f"SELECT * FROM public.article_status WHERE article_id='{records[0][0]}'")
            records = list(cursor.fetchall())
            if records[0][1] == 1:
                return flask.render_template('draft.html', ban=ban, a=roles[0], m=roles[1], w=roles[2], new_publish=new_publish, text=text, title=title, author=author)
            elif records[0][1] == 2:
                return flask.render_template('draft.html', ban=ban, a=roles[0], m=roles[1], w=roles[2], new_publish=new_publish, text=text, title=title, author=author, publish=1)
            elif records[0][1] == 3:
                return flask.render_template('draft.html', ban=ban, a=roles[0], m=roles[1], w=roles[2], new_publish=new_publish, text=text, title=title, author=author, aprooved=1)
            else:
                return flask.render_template('draft.html', ban=ban, a=roles[0], m=roles[1], w=roles[2], new_publish=new_publish, text=text, title=title, author=author, reason=reason, denied=1)
    else:
        return flask.redirect(flask.url_for('.home'))

def authorization_check_article(article_name):
    ban = flask.session.get('ban')
    user_roles = flask.session.get('role')
    if user_roles == None:
        return flask.redirect(flask.url_for('.sign_in_start'))
    else:
        new_publish = f"({check_writer_uploads()})"
        cursor.execute(f"SELECT * FROM public.article WHERE name='{article_name}' and isdeleted = {False} ")
        records = list(cursor.fetchall())
        if records == []:
            return flask.render_template("article.html", a = user_roles[0], m = user_roles[1], w = user_roles[2], ban = ban, new_publish=new_publish, article_name=article_name, no_article=1)
        else:
            user_id = flask.session.get('user')
            article_id = records[0][0]
            flask.session['article_id'] = article_id
            cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={article_id}")
            check = list(cursor.fetchall())
            status_id = check[0][1]
            #checking if article is aprooved.
            if status_id != 3:
                cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id} and user_id={user_id}")
                check = list(cursor.fetchall())
                if check != []:
                    return flask.redirect(flask.url_for('.draft_start'))
                else:
                    if status_id == 1:
                        return flask.render_template("article.html", a = user_roles[0], m = user_roles[1], w = user_roles[2], ban = ban, new_publish=new_publish, article_name=article_name, not_published=1)
                    elif status_id == 2:
                        return flask.render_template("article.html", a = user_roles[0], m = user_roles[1], w = user_roles[2], ban = ban, new_publish=new_publish, article_name=article_name, not_aprooved=1)
                    else:
                        desc = records[0][3]
                        return flask.render_template("article.html", a = user_roles[0], m = user_roles[1], w = user_roles[2], ban = ban, new_publish=new_publish, article_name=article_name, denied=1, reason=desc)
            else:
                #here must be tags
                title = records[0][2]
                path = f".\\articles\\{article_name}.txt"
                text = form_text(path)
                topic = get_topic(article_id)
                rate = get_rating(article_id)
                user_review=review_check(user_id, article_id, article_name)
                cursor.execute(f"UPDATE public.user_read SET isread={True} WHERE user_id={user_id} and article_id={article_id} and isread={False}")
                conn.commit()
                return flask.render_template("article.html", a = user_roles[0], m = user_roles[1], w = user_roles[2], ban = ban, new_publish=new_publish, article_name=article_name, title=title, text=text, rate=rate, user_rate=user_review[0], user_review=user_review[1], user_date=user_review[2])
            #path = f".\\reviews\\{article_name}.txt"
            #reviews = form_text(path)
            
        
def check_writer_uploads():
    cursor.execute(f"SELECT * FROM public.article_status WHERE status_id=2")
    records = list(cursor.fetchall())
    res = 0
    for i in records:
        res+=1
    return res

def review_check(user_id, article_id, article_name):
    cursor.execute(f"SELECT * FROM public.rating WHERE user_id={user_id} and article_id={article_id} and isdeleted={False}")
    records = list(cursor.fetchall())
    rate = None
    review = None
    date = None
    if records != []:
        rate = records[0][4]
        date = records[0][3]
        path = f".\\reviews\\{article_name}.txt"
        with open(path, "r") as text_file:
            lines = text_file.readlines()
        text_file.close()
        formed_id = str(user_id)
        for line in lines:
            wrong = 1
            for i in range(len(formed_id)):
                if line[i] == formed_id[i]:
                    wrong = 0
                else:
                    wrong = 1
                    break
            if wrong == 0:
                review = line[len(formed_id)+1:]
                break
    return [rate, review, date]

def is_author(article_id, user_id):
    cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id='{article_id}' and user_id='{user_id}'")
    records = list(cursor.fetchall())
    if records[0][2] == True:
        return 1
    else:
        return 0

"""
def workshop_check(user_id, roles, no_article):
    new_publish = f"({check_writer_uploads()})"
    ban = flask.session.get('ban')
    cursor.execute(f"SELECT * FROM public.article_writer WHERE user_id={user_id}")
    records = list(cursor.fetchall())
    if records == []:
        return flask.render_template('workshop.html', a = roles[0], m = roles[1], w = roles[2], new_publish=new_publish)
    else:
        first, second, third = None, None, None
        for i in range (len(records)-1, -1, -1):
            article_id = records[i][0]
            cursor.execute(f"SELECT * FROM public.article WHERE id={article_id}")
            recs = list(cursor.fetchall())
            if recs != []:
                if i == len(records)-1:
                    first = recs[0][1]
                elif i == len(records)-2:
                    second = recs[0][1]
                elif i == len(records)-3:
                    third = recs[0][1]
                else: 
                    break
            else:
                break
        return flask.render_template('workshop.html', ban=ban, a=roles[0], m=roles[1], w=roles[2], new_publish=new_publish, no_article=no_article)
"""


#FORM
def form_text(path):
    check = 1
    with open(path, "r") as text_file:
        lines = text_file.readlines()
    text_file.close()
    if path[2:10] == 'articles':
        return form_article(lines)
    #else:
        #return form_reviews(lines)

def form_article(lines):
    if lines == []:
        return None
    else:
        check = 1
        new_lines = ""
        for line in lines:
            if line != "\n" or check == 1:
                new_lines += line
                check = 0
            else:
                check = 1
        #print(new_lines)
        return new_lines

def form_read_colums(article_id):
    cursor.execute(f"SELECT * FROM public.users")
    records = list(cursor.fetchall())
    for rec in records:
        cursor.execute(f"INSERT INTO public.user_read (user_id, article_id, isread) VALUES ({rec[0]}, {article_id}, {False})")
    conn.commit()
    return 0

"""
def form_reviews(article_id):
    res = ""
    cursor.execute(f"SELECT * FROM public.rating WHERE article_id={article_id} and isdeleted={False}")
    rating = list(cursor.fetchall())
    if rating == []:
        return None
    else:
        for i in (len(rating)-1, 0, -1):
            cursor.execute(f"SELECT * FROM public.users WHERE id={rating[i][1]} and isbanned={False}")
            records = list(cursor.fetchall())
            username = records[0][1]
            fullname = records[0][3]

def build_html(direction):
    path = f".\\templates\\{direction}.html"
    with open(path, "r") as text_file:
        lines = text_file.readlines()
    text_file.close()
    rem = 0
    res = ""
    for i in range (len(lines)):
        if rem == 0:
            res += lines[i]
        if lines[i] == "\t\t\t\tvar myArray = [\n":
            rem = 1
        elif lines[i] == "\t\t\t\t]\n":
            if direction == 'home':
                res += select_table_desc() + lines[i]
            else:
                res += select_table_published() + lines[i]
            rem = 0
    with open(path, "w") as file:
        file.write(res)
    file.close()
    return 0
"""
#GET
def get_topic(article_id):
    cursor.execute(f"SELECT * FROM public.article_topic WHERE article_id={article_id}")
    article_desc = list(cursor.fetchall())
    cursor.execute(f"SELECT * FROM public.topic WHERE id={article_desc[0][1]}")
    topic_desc = list(cursor.fetchall())
    topic = topic_desc[0][1]
    return topic

def get_rating(article_id):
    cursor.execute(f"SELECT * FROM public.rating WHERE article_id={article_id} and isdeleted={False}")
    rating_desc = list(cursor.fetchall())
    count = 0
    for log in rating_desc:
        count += log[4]
    if count!=0:
        reviews = round(count/len(rating_desc), 1)
    else:
        reviews = 0
    return reviews

def get_current_date():
    time = str(datetime.datetime.now())
    time = time[0:10]
    res = ""
    for char in time:
        if char != "-":
            res += char
        else:
         res += '.'
    return res


#SELECT
def select_role(roles):
    res = [0, 0, 0, 0]
    for role in roles:
        if role == 1:
            res[0]=1
        elif role == 2:
            res[1]=1
        elif role == 3:
            res[2]=1
        elif role == 4:
            res[3]=1
    return res

def select_table_desc():
    cursor.execute(f"SELECT * FROM public.article WHERE isdeleted={False}")
    records = list(cursor.fetchall())
    array = []
    for rec in records:
        article_id = rec[0]
        name = rec[1]
        date = rec[5]
        cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={article_id}")
        check = list(cursor.fetchall())
        if check[0][1] == 3:
            cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id}")
            article_desc = list(cursor.fetchall())
            authors = ""
            for log in article_desc:
                cursor.execute(f"SELECT * FROM public.users WHERE id={log[1]}")
                desc = list(cursor.fetchall())
                authors += desc[0][3] + ", "
            authors=authors[0:len(authors)-2]
            topic = get_topic(article_id)
            reviews = get_rating(article_id)
            cursor.execute(f"SELECT * FROM public.user_read WHERE article_id={article_id} and isread={True}")
            views_check = list(cursor.fetchall())
            views = len(views_check)
            array += {'name':name, 'author': authors, 'topic': topic, 'views': views, 'reviews': reviews, 'date': date},
    return array

def select_table_published():
    cursor.execute(f"SELECT * FROM public.article_status WHERE status_id={2}")
    records = list(cursor.fetchall())
    array = []
    for rec in records:
        article_id = rec[0]
        cursor.execute(f"SELECT * FROM public.article WHERE id={article_id}")
        article_desc = list(cursor.fetchall())
        name = article_desc[0][1]
        date = article_desc[0][5]
        cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id}")
        check = list(cursor.fetchall())
        authors = ""
        for log in check:
            cursor.execute(f"SELECT * FROM public.users WHERE id={log[1]}")
            desc = list(cursor.fetchall())
            authors += desc[0][3] + ", "
        authors=authors[0:len(authors)-2]
        topic = get_topic(article_id)
        reviews = '-'
        views = 0
        array += {'name': name, 'author': authors, 'topic': topic, 'views': views, 'reviews': reviews, 'date': date},
    return array

def select_table_personal():
    user_id = flask.session.get('user')
    cursor.execute(f"SELECT * FROM public.article_writer WHERE user_id={user_id}")
    records = list(cursor.fetchall())
    array = []
    for rec in records:
        article_id = rec[0]
        cursor.execute(f"SELECT * FROM public.article WHERE id={article_id}")
        article_desc = list(cursor.fetchall())
        name = article_desc[0][1]
        date = article_desc[0][5]
        cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id}")
        check = list(cursor.fetchall())
        authors = ""
        for log in check:
            cursor.execute(f"SELECT * FROM public.users WHERE id={log[1]}")
            desc = list(cursor.fetchall())
            authors += desc[0][3] + ", "
        authors=authors[0:len(authors)-2]
        topic = get_topic(article_id)
        reviews = get_rating(article_id)
        cursor.execute(f"SELECT * FROM public.user_read WHERE article_id={article_id} and isread={True}")
        views_check = list(cursor.fetchall())
        views = len(views_check)
        array += {'name': name, 'author': authors, 'topic': topic, 'views': views, 'reviews': reviews, 'date': date},
    return array

def select_reviews():
    #author, username, rate, review, date
    user_id = flask.session.get('user')
    article_id = flask.session.get('article_id')
    array = []
    cursor.execute(f"SELECT * FROM public.article WHERE id={article_id}")
    records = list(cursor.fetchall())
    if records != []:
        article_name = records[0][1]
        path = f".\\reviews\\{article_name}.txt"
        with open(path, "r") as text_file:
            lines = text_file.readlines()
        text_file.close()
        for line in lines:
            author_id = ""
            for i in range(len(line)):
                if line[i] == ':':
                    start = i
                    break
                else:
                    author_id += line[i]
            if int(author_id) == int(user_id):
                continue
            else:
                review = line[start+1:]
                review = review[0:len(review)-2]
                cursor.execute(f"SELECT * FROM public.users WHERE id={author_id}")
                author_desc = list(cursor.fetchall())
                username = author_desc[0][1]
                author = author_desc[0][3]
                cursor.execute(f"SELECT * FROM public.rating WHERE user_id={author_id} and article_id={article_id}")
                rating_desc = list(cursor.fetchall())
                rate = rating_desc[0][4]
                date = rating_desc[0][3]
                array += {'author': author, 'username': username, 'rate': rate, 'comment': review, 'date': date},
    return array

#for selecting articles aprooved recently
def select_table_recent():
    current_date = get_current_date() # get date
    user_id = flask.session.get('user') # get user id
    cursor.execute(f"SELECT * FROM public.article WHERE isdeleted={False}") # selecting all not deleted articles
    records = list(cursor.fetchall())
    array = []
    for rec in records:
        article_id = rec[0] # get article id
        name = rec[1] # get article name
        date = rec[5] # get date of aprooving article
        cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={article_id}") # selecting articles's status
        check = list(cursor.fetchall())
        cursor.execute(f"SELECT * FROM public.user_read WHERE user_id={user_id} and article_id={article_id}") # checking which articles user has already read
        read_check = list(cursor.fetchall())
        if check[0][1] == 3 and (read_check[0][2] != True or rec[5] == current_date): # checking if article is aprooved, if user read current article or article was aprooved today  
            cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id}") # selecting article's authors
            article_desc = list(cursor.fetchall())
            authors = ""
            for log in article_desc: # getting authors of article
                cursor.execute(f"SELECT * FROM public.users WHERE id={log[1]}")
                desc = list(cursor.fetchall())
                authors += desc[0][3] + ", "
            authors=authors[0:len(authors)-2]
            topic = get_topic(article_id) # getting article's topic
            reviews = get_rating(article_id) # getting article's rating 
            cursor.execute(f"SELECT * FROM public.user_read WHERE article_id={article_id} and isread={True}")
            views_check = list(cursor.fetchall())
            views = len(views_check) # getting article's views
            array += {'name': name, 'author': authors, 'topic': topic, 'views': views, 'reviews': reviews, 'date': date}, # form array
    return array
        


"""  
TESTS
if __name__ == '__main__':
    time = str(datetime.datetime.now())
    time = time[0:10]
    print(time)
    array = select_table_desc()
    print(array)
    conn = psycopg2.connect(database="server_db",
                                user="postgres",
                                password="postgres",
                                host="localhost",
                                port="5432")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM role_user WHERE user_id=4")
    records = list(cursor.fetchall())
    for i in range(len(records)):
        print(records[i], i)

if __name__ == '__main__':
    path = f".\\articles\\test3.txt"
    with open(path, "r") as text_file:
        lines = text_file.readlines()
    text_file.close()
    print(lines)
    form_text(path)
    with open(".\\reviews\\test2.txt", "w") as file:
        file.write("")
    file.close()
    with open(".\\reviews\\test3.txt", "w") as file:
        file.write("")
    file.close()
    with open(".\\reviews\\denis.txt", "w") as file:
        file.write("")
    file.close()
    path = f".\\articles\\copy.txt"
    with open(path, "w") as file:
        file.write("Your text goes here. And reads like this.")
    text_file = open(path, "r")
    lines = text_file.readlines()
    print(lines[0])
    with open("copy.txt", "w") as file:
        file.write("Your text goes here")
    conn = psycopg2.connect(database="server_db",
                                user="postgres",
                                password="postgres",
                                host="localhost",
                                port="5432")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM role_user WHERE user_id=4")
    records = list(cursor.fetchall())
"""
    
    

 