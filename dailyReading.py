import json
import os
from datetime import datetime

import pygit2
import requests
import urllib3
from bs4 import BeautifulSoup
from github import Github

import wisecreator.wisecreate

repoName = os.environ['REPO_NAME']
repoToken = os.environ['GITHUB_TOKEN']
domain = os.environ['HIDE_DOMAIN']
userName = os.environ['USER_NAME']
email = os.environ['EMAIL']

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/11.1 Safari/605.1.15'}
http = urllib3.PoolManager(10, headers=headers)
urllib3.disable_warnings()


def get_element_from_request(url, element, class_):
    response = http.request('GET', url)
    soup = BeautifulSoup(response.data.decode('utf-8'), "html5lib")
    return soup.find(element, class_=class_)


def get_meta_data():
    container = get_element_from_request(domain + '/nc/daily', 'div', 'dailyV2__free-book')

    title = container.find('div', 'dailyV2__free-book__title').string.strip()
    author = container.find('div', 'dailyV2__free-book__author').string.strip()
    description = container.find('div', 'dailyV2__free-book__description').string.strip()
    cta = container.find('div', 'dailyV2__free-book__cta').a['href']
    img_url = container.find('img')['src']

    return title, author, description, cta, img_url


def get_article(cta):
    return str(get_element_from_request(domain + cta, 'article',
                                        'shared__reader__blink reader__container__content')).strip()


def get_chapter_ids(cta):
    chapter_no_2_chapter_id = {}
    menu_list = get_element_from_request(f'{domain}{cta}', "div",
                                         "reader__container__chapters__menu__inside")
    for li in menu_list.find_all('li'):
        chapter_no_2_chapter_id[li.attrs.get('data-chapterno')] = li.attrs.get('data-chapterid')
    return chapter_no_2_chapter_id


def get_book_id(cta):
    reader_contrainer = get_element_from_request(f'{domain}{cta}', "div", "reader__container")
    return reader_contrainer.attrs.get('data-book-id')


def get_audio_links(book_id, chapterids):
    chapter_no_2_audio_link = {}
    for chapterNo, chapterid in chapterids.items():
        response = requests.get(f'{domain}/api/books/{book_id}/chapters/{chapterid}/audio')
        chapter_no_2_audio_link[chapterNo] = json.loads(response.content).get('url')
    return chapter_no_2_audio_link


def write_audio_file(audio_links, directory, title):
    for chapterNo, audio_link in audio_links.items():
        write_to_file(os.path.join(directory, f'{title}-{chapterNo}.mp4'),
                      requests.get(audio_link).content, 'wb')


def run():
    print('Fetching content...', end='')
    title, author, description, cta, img_url = get_meta_data()
    html_article = get_article(cta)
    output_html = f'<img src="{img_url}"><h1>{title}</h1><h2>{author}</h2><p>{description}</p>{html_article}'

    date = datetime.now().strftime('%Y%m%d')
    directory = 'clone/blinks/' + f'{date[:4]}' + '/' + title.replace(" ", "_")
    if not os.path.exists(directory):
        os.makedirs(directory)
    commitMessage = f'{title} by {author}'
    html_file_name = os.path.join(directory, f'{date}-{title.replace(" ", "_")}-{author.replace(" ", "_")}.html')

    print('Building output...', end='')
    write_to_file(html_file_name, output_html, 'w')
    wisecreator.wisecreate.main(f'{html_file_name}')
    os.remove(html_file_name)
    write_audio_file(get_audio_links(get_book_id(cta), get_chapter_ids(cta)), directory, title.replace(" ", "_"))
    return commitMessage


def write_to_file(file_name, output, option):
    file = open(file_name, option)
    file.write(output)
    file.close()


def get_clone_repo():
    g = Github(repoToken)
    repo = g.get_user().get_repo(repoName)
    repo_clone = pygit2.clone_repository(repo.git_url, 'clone')
    repo_clone.remotes.set_url("origin", repo.clone_url)
    return repo_clone


def commit_and_push(repo_clone, commit_message):
    index = repo_clone.index
    index.add_all()
    index.write()
    author = pygit2.Signature(userName, email)
    commiter = pygit2.Signature(userName, email)
    tree = index.write_tree()
    repo_clone.create_commit('refs/heads/master', author, commiter, commit_message, tree,
                             [repo_clone.head.get_object().hex])
    remote = repo_clone.remotes["origin"]
    credentials = pygit2.UserPass(repoToken, 'x-oauth-basic')
    remote.credentials = credentials
    callbacks = pygit2.RemoteCallbacks(credentials=credentials)
    remote.push(['refs/heads/master'], callbacks=callbacks)


if __name__ == '__main__':
    clone = get_clone_repo()
    commit_and_push(clone, run())
