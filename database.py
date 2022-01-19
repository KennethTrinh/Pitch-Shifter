import sqlite3
import os
from datetime import datetime


class Database:

    def __init__(self):

        file_ = ''
        files = [f for f in os.listdir() if f.endswith('.db')]

        if len(files) == 1:
            file_ = files[0]
            self.reset = False
        elif len(files) == 0:
            file_ = f'music_record.db'
            self.reset = True


        self.conn = sqlite3.connect(file_)
        self.cur = self.conn.cursor()

        if self.reset:
            self.cur.executescript(""" drop table if exists Musics;
                                    CREATE TABLE Musics( M_Name text not null,
                                    M_Path text not null); """
            )
            self.conn.commit()

    def print_contents(self):
        print('All Music')
        self.cur.execute("SELECT * FROM Musics")
        result = self.cur.fetchall()
        for row in result:
            print(row)

    def add_to_music(self, music, path):
        self.cur.execute("SELECT * FROM Musics WHERE M_Name = :name", {'name': music})
        result = self.cur.fetchall()
        if len(result) >0:
            return -1
        self.cur.execute("""INSERT INTO Musics (M_Name, M_Path) VALUES
            (:m_name, :m_path)""", {'m_name': music, 'm_path': path})
        self.conn.commit()
        return 0

    def del_from_music(self, music):
        self.cur.execute("DELETE FROM Musics WHERE M_Name = :m_name", {'m_name': music})
        self.conn.commit()

    def get_musics(self):
        self.cur.execute("SELECT * FROM Musics")
        return self.cur.fetchall()

    def get_directory(self, music):
        self.cur.execute("SELECT M_Path FROM Musics WHERE M_Name = :m_name", {'m_name': music})
        return self.cur.fetchall()[0][0]
