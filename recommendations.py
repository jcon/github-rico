# The MIT License
# 
# Copyright (c) 2009 Jim Connell
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from __future__ import with_statement
import sys 
import operator
import os.path
from datetime import datetime
import logging

#"""
#First attempt at a complete trivial version of the algorithm.  I'd be surprised
#if it beats 20% :)
#"""

USERCACHE_PATH = os.path.join('output', 'usercache.txt')
DATA_PATH = os.path.join('data', 'data.txt')
REPOS_PATH = os.path.join('data', 'repos.txt')
TEST_PATH = os.path.join('data', 'test.txt')

logger = logging.getLogger("github-rico")
def enable_logging():
    """
    Configures console logging for the application's logger.  By
    default, logging operations will not output log statements
    unless the logger has been configured.
    """
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)
enable_logging()

def file_next():
    with open(DATA_PATH, 'r') as f:
        for line in f:
            tuple = map(int, line[:-1].split(':'))
            yield tuple 

data_generator = file_next

def userlist_next():
    with open(TEST_PATH, 'r') as f:
        for line in f:
            uid = line[:-1]
            yield int(uid)

def parse_data():
    users = {}
    projects = {}

    for user, project in data_generator():
        if user not in users:
            users[user] = []
        if project not in projects:
            projects[project] = []
        users[user].append(project)
        projects[project].append(user)

    return users, projects

class RepoLookup:
    def __init__(self):
        self.map = {}
        with open(REPOS_PATH, 'r') as f:
            for line in f:
                (project_id, data) = line[:-1].split(':')
                fields = data.split(',')
                map = {
                    'url': fields[0],
                    'founder': fields[0].split('/')[0]
                    }
                if 3 == len(fields):
                    map['parent'] = int(fields[2])
                self.map[int(project_id)] = map

    def getkey(self, project_id, key):
        value = None
        if project_id in self.map and key in self.map[project_id]:
            value = self.map[project_id][key]
        return value

    def parent(self, project_id):
        return self.getkey(project_id, 'parent')

    def url(self, project_id):
        return self.getkey(project_id, 'url')

    def founder(self, project_id):
        return self.getkey(project_id, 'founder')

class UserCache:
    def __init__(self, users, projects, clean=False):
        self.users = users
        self.projects = projects
        self.clean = clean
        if self.clean or not os.path.exists(USERCACHE_PATH):
            self.create_cache()
        else:
            self.read_cache()
        logger.debug("initalized with %d keys" % len(self.usercache.keys()))

    def __getitem__(self, k):
        return self.usercache[k]

    def __contains__(self, k):
        return k in self.usercache

    def read_cache(self):
        usercache = {}
        with open(USERCACHE_PATH, 'r') as f:
            for line in f:
                user_id, similar_users = line[:-1].split(':')
                if '' != similar_users:
                    l = map(int, similar_users.split(','))
                else:
                    l = []
                usercache[int(user_id)] = l
        self.usercache = usercache

    def create_cache(self):
        usercache = {}
        users = self.users.items()
        total = len(users)
        c = 0
        with open(USERCACHE_PATH, 'w') as f:
            for user_id, projects in users:
                similar_users = {}
                for project_id in projects:
                    for uid in self.projects[project_id]:
#                        if uid == user_id:
#                            continue
                        if uid not in similar_users:
                            similar_users[uid] = 0
                        similar_users[uid] = similar_users[uid] + 1
                items = sorted(similar_users.items(), key=operator.itemgetter(1), reverse=True)
#                 for item in items:
#                     logger.debug("found %s:%s" % item)
                usercache[user_id] = [x[0] for x in items[:30]]
                f.write("%d:%s\n" % (user_id, ",".join(map(str, usercache[user_id]))))
                c = c + 1
                if c % 1000 == 0:
                    logger.debug("seed: %d of %d" % (c, total))

        self.usercache = usercache

class Recommendations:
    def __init__(self, clean=False):
        self.clean = clean

    def setup(self):
        self.users, self.projects = parse_data()
        self.usercache = UserCache(self.users, self.projects)
        self.repoLookup = RepoLookup()

    def rank_projects(self, users):
        c = 0
        for user_id in users:
            if user_id not in self.users:
                logger.warn("cannot find test user %d in user cache" % user_id)
                continue
            similar_users = self.usercache[user_id]
            guesses = {}
            project_set = set(self.users[user_id])
            founder_set = set([self.repoLookup.founder(pid) for pid in self.users[user_id]])
            for uid in similar_users:
                if uid == user_id: continue
                
#                print self.users
#                print("looking for uid=%s" % uid)
                if uid not in self.users:
                    logger.warn("cannot find related user %d in user map" % uid)
                    continue

                for pid in self.users[uid]:
                    if pid in project_set:
                        continue
                    if pid not in guesses:
                        guesses[pid] = 0
                    parent = self.repoLookup.parent(pid)
                    founder = self.repoLookup.founder(pid)
                    if founder in founder_set:
#                        logger.info('ranking %d higher because of founder %s' % (pid, founder))
                        guesses[pid] = guesses[pid] + 5
                    elif parent != None and parent in project_set:
#                        logger.info('ranking %d higher because of parent %d' % (pid, parent))
                        guesses[pid] = guesses[pid] + 3
                    else:
                        guesses[pid] = guesses[pid] + 1

            items = sorted(guesses.items(), key=operator.itemgetter(1), reverse=True)
            items = [x[0] for x in items[:10]] 

            c = c + 1
            if c % 100 == 0:
                print("Finished %d" % c)
            yield user_id, items


# users
# languages
# parent

def main():
    start = datetime.now()
    a = Recommendations()
    a.setup()
    user_list = userlist_next()
    with open("results.txt", "w") as f:
        for user, guesses in a.rank_projects(user_list):
            f.write("%s:%s\n" % (str(user), ",".join(map(str, guesses))))

    end = datetime.now() - start
    print("done in %s" % end)

if __name__ == "__main__":
    main()
