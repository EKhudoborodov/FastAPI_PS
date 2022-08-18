# ТЗ
Предметная область:
  Платформа для написания и публикации статей.
Задача:
  Реализовать сервер backend для платформы, отвечающий следующим требованиям:
  1) Сервер должен обеспечивать регистрацию и авторизацию пользователей
  2) Сервер должен поддерживать разграничение пользователей по ролям:
    * Администратор -- полный доступ ко всем функциям, может назначать роли. Включает в себя все роли.
    * Модератор -- проверяет новые статьи и может их либо одобрить, либо отклонить. Проверяет комментарии.
    * Писатель -- может создавать новые статьи.
    * Обычный пользователь (читатель) -- может читать статьи и оставлять комментарии.
     Не зарегистрированный пользователь не должен иметь доступа к системе.
  3) Статья может находиться в следющих состояниях:
    * Черновик (Статья, добавленная Писателем, но ещё не опубликованная. Только Писатель может поменять состояние на Опубликована)
    * Опубликована (Опубликованная статья, только Модератор видит опубликованные статьи)
    * Одобрена (Статья, одобренная Модератором, видна всем читателям)
    * Отклонена (Отклонённая Модератором статья, к ней должен быть прикреплён комментарий с причиной отклонения)
  4) У одной статьи может быть несколько авторов и редакторов.
  5) У одного пользователя может быть несколько ролей.
  6) Сервер должен поддерживать процесс редактирования статьи в состоянии Черновик.
  7) Должна быть возможность блокировки пользователей
  8) Статья, находящаяся в состоянии Одобрена, не должна редактироваться, однако её автор может убрать её в черновик.
  Дополнительные требования:
  9) Сервер должен использовать защищённые версии протоколов (https, wss и другие)
  10) Должны поддерживаться множественные сессии пользователей, с возможностью отключить все и все, кроме текущей.
  11) Сервер должен поддерживать связывание аккаунтов (авторизация через сторонние сервисы (пример: Яндекс ID, ВКонтакте, Mail.ru))
  12) Сервер должен поддерживать оценки статей
  13) Сервер должен предоставлять информацию о новых одобренных статьях 
  14) Сервер должен поддерживать поиск статей по следующим показателям:
    * По оценкам читателей
    * По количеству читателей
    * По названию
    * По содержимому
    * По ключевым словам
    * По авторам 
    * По дате публикации
  15) Статьи должны группироваться по секциям

# FastAPI_PS
Framework: FastAPI;
Библиотеки: fastapi, pydantic, enum, uvicorn, os, psycopg2, datetime;
База данных: server_db;
Таблицы:
  1) article: {id, name, title, description, isdeleted}
  2) article_hashtag {article_id, hashtag}
  3) article_status: {article_id, status_id}
  4) article_topic: {article_id, topic_id}
  5) article_writer: {article_id, user_id, isauthor}
  6) events: {id, user_id, event, description, date, time}
  7) hashtag: {id, name}
  8) rating: {id, user_id, article_id, date, rate, isdeleted}
  9) role_user: {user_id, role_id}
  10) status: {id, name, description}
  11) topic: {id, name}
  12) user_read {user_id, article_id, isread}
  13) users: {id, login, password, fullname, isbanned}

# Старт
Для запуска необходимо запустить команду "pip install -r requirements.txt".
При первом запуске сервера запустить reboot.py "python reboot.py".
Затем запустить server.py "python server.py".
![image](https://user-images.githubusercontent.com/90326938/185350116-eb1bb26d-622f-4644-ae10-11686e2150b4.png)
В файле main.py содержатся запросы. Библиотеки для файла main.py:
![image](https://user-images.githubusercontent.com/90326938/185352030-36308bcd-25f4-4ff7-bac8-0c6ec7b12224.png)
В файле functional.py содержатся функции всех запросов. Библиотеки для файла functional.py
![image](https://user-images.githubusercontent.com/90326938/185352289-06ac3fde-20e2-4641-b30f-f1be78610ac5.png)
Файл exceptions.py содержит функцию вызова ошибки.
![image](https://user-images.githubusercontent.com/90326938/185352983-6008d167-eee0-4118-bed5-c65e9e738a5c.png)
Файл classes.py содержит классы для запросов ввода.
![image](https://user-images.githubusercontent.com/90326938/185353719-1139a0f2-7214-4932-9ef1-61010d547dca.png)
![image](https://user-images.githubusercontent.com/90326938/185353832-30c0ab6e-6a07-445c-9967-cb32441e3a8a.png)

# Авторизация
Запросы в main.py
![image](https://user-images.githubusercontent.com/90326938/185355606-f84e745c-2dab-4680-95d0-c47680e7f9cb.png)
Реализация в functional.py
![image](https://user-images.githubusercontent.com/90326938/185356262-bc8ad11e-0c91-4dc0-8981-aac88cb5a54b.png)
Вид в документации (FastAPI - Swagger UI)
![image](https://user-images.githubusercontent.com/90326938/185348472-399bff33-6893-44c8-9d2e-12c7f4b84ec4.png)

# Поиск и чтение статей
Запросы в main.py
![image](https://user-images.githubusercontent.com/90326938/185356826-f328eade-904a-4a9b-bfa2-26e696bf5a85.png)
Реализация выбора статей из базы данных в functional.py
![image](https://user-images.githubusercontent.com/90326938/185359503-888b8526-d4c4-4493-8514-4dcfdd695643.png)
![image](https://user-images.githubusercontent.com/90326938/185359748-f4b6b0e5-8af0-4c29-a131-b7dee6df6d36.png)
Реализация поиска статей
![image](https://user-images.githubusercontent.com/90326938/185360286-444c1923-ad94-4aeb-af25-bba61a251890.png)
![image](https://user-images.githubusercontent.com/90326938/185360491-0abd8a22-62c8-4338-acdf-a781f6500367.png)
![image](https://user-images.githubusercontent.com/90326938/185360630-2b6433b5-4bcc-4d97-abb4-9ca5073a2c00.png)
Сортировка статей по секциям
![image](https://user-images.githubusercontent.com/90326938/185360696-fc91a5e6-ff91-4237-864d-87ddf3ec9dec.png)
Реализация чтения статьи
![image](https://user-images.githubusercontent.com/90326938/185361435-f9262b7a-c101-495a-b465-79b736729787.png)
Реализация оценки статей
![image](https://user-images.githubusercontent.com/90326938/185361746-d3dc5d5f-cfde-46d5-b625-6eac046414b5.png)
![image](https://user-images.githubusercontent.com/90326938/185361624-d615e446-baa6-4813-b289-80a31631af0e.png)
Вид
![image](https://user-images.githubusercontent.com/90326938/185362679-651516f7-eb84-4813-a89e-fe9a035706dd.png)

# Настройки (Для администратора)
Запросы в main.py
![image](https://user-images.githubusercontent.com/90326938/185363479-e910abc9-9ae9-4ab4-a016-78c5a9e1f95b.png)
Реализация обновления ролей пользователя в functional.py
![image](https://user-images.githubusercontent.com/90326938/185363168-3c8975eb-bf73-429b-ae21-a2abb0fe6cb6.png)
Реализация остановки сессий (Если сессии остановлены пользователи не смогут пользоваться сервисом в течение часа)
![image](https://user-images.githubusercontent.com/90326938/185363930-73124ba4-7b06-4f6e-bb2b-354f8c66e317.png)
![image](https://user-images.githubusercontent.com/90326938/185364110-455a3ee8-bc97-43bf-b876-8d92ae66d4fc.png)
Вид
![image](https://user-images.githubusercontent.com/90326938/185364694-21fcbba2-477d-4a07-aff2-4adde020d5b1.png)

# Создание и редактирование статей
Запросы в main.py
![image](https://user-images.githubusercontent.com/90326938/185366321-ed0ab5b6-09bb-49ec-a456-8312a458da89.png)
Реализация получения списка статей пользователя и информации о них в functional.py
![image](https://user-images.githubusercontent.com/90326938/185366874-9dcc81ce-259c-40fc-a1e6-1d3054da8f62.png)
Реализация создания новой статьи
![image](https://user-images.githubusercontent.com/90326938/185367210-74b58aec-8cf6-45e4-b450-effe99e908a1.png)
Реализация добавления соавторов и редакторов статьи
![image](https://user-images.githubusercontent.com/90326938/185368676-c4b21e33-8434-48cd-b288-c2e02918d1e7.png)
![image](https://user-images.githubusercontent.com/90326938/185368787-aec70f4b-3501-4399-873f-b26cbfe5dd55.png)
Реализация получения информации о статье
![image](https://user-images.githubusercontent.com/90326938/185369100-ad08831d-1938-43c1-a13a-e5b0560016fb.png)
Реализация изменения статьи
![image](https://user-images.githubusercontent.com/90326938/185369309-410f4dc6-aeed-48b5-9042-9b214d4a9924.png)
![image](https://user-images.githubusercontent.com/90326938/185369396-87be72d1-ce98-47c0-82a5-2dafefa19461.png)
Вид
![image](https://user-images.githubusercontent.com/90326938/185369616-49709b6d-60fc-40b8-843d-ab5066b907f0.png)

# Рассмотр статей модераторами
Запросы в main.py
![image](https://user-images.githubusercontent.com/90326938/185369902-a916bd8c-cc97-4430-a826-dddec1e9ab94.png)
Реализация получения списка опубликованных статей в functional.py
![image](https://user-images.githubusercontent.com/90326938/185370110-13422fb0-51be-47b1-8591-b5c7d7d6d818.png)
Реализация чтения опубликованной статьи
![image](https://user-images.githubusercontent.com/90326938/185370288-bcd6b0fa-157d-44e0-a794-3e8fc68fdd34.png)
Реализация одобрения и отклонения статьи
![image](https://user-images.githubusercontent.com/90326938/185370582-b7c02fb6-1746-49de-a90a-b46ef934c022.png)
Вид
![image](https://user-images.githubusercontent.com/90326938/185370686-13433930-4668-4f35-828d-e96f849595d2.png)
