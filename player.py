from tkinter import *
import tkinter.ttk as ttk
from tkinter import filedialog
import database
import time
from pitch_shift import PitchShifter
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
NavigationToolbar2Tk)
import matplotlib.animation as animation
import matplotlib.pyplot as plt


# App Database
playlists_record = database.Database()
# Directory to get musics from
songs_main_dir = '/Users/kennethtrinh/Desktop/pitchshift/'



def add_song():
    global song_box
    song = filedialog.askopenfilename(initialdir=songs_main_dir, title="Choose A Song", filetypes=(("mp3 Files", "*.mp3"), ("wav Files", "*.wav")))
    # Getting the path of the .mp3 file
    song_dir = song.split("/")
    song_dir.pop(len(song_dir)-1)
    song_file = song_dir[0]
    song_dir.pop(0)
    for elem in song_dir:
        song_file = song_file + "/" + elem
    song_file = song_file + "/"
    # Saving path of the .mp3 file in the path List
    # Strip out the directory info and .mp3 extension from the song name
    song = song.replace(song_file, "").replace(".mp3", "")
    # Add song to list box
    if playlists_record.add_to_music(song, song_file) == -1:
        print('cannot add song, choose different name')
        return
    song_box.insert(END, song)


def delete_song():
    global song_box
    # Getting song index in order to choose the right path for it in the Path List
    stop()
    song_idx = song_box.index(ACTIVE)
    song = song_box.get(ACTIVE)
    song_box.delete(song_idx)
    song_box.activate(song_idx-1 )
    song_box.selection_set(song_idx-1, last=None)
    playlists_record.del_from_music(song)
def display_songs():
    global song_box, previous_pitch
    for elem in playlists_record.get_musics():
        song_box.insert(END, elem[0])
        print(elem)
    if song_box.size() >0:
        song_box.activate(0)
        song_box.selection_set(0, last=None)
        song = song_box.get(0)
        previous_pitch = 2**(0/12)


def back():
    global song, song_box, music_slider, music_label_text, loaded, previous_pitch
    music_slider.config(value=0)
    music_label_text.set('00:00')
    try:
        previous_song = (song_box.curselection()[0] - 1 ) % song_box.size()
    except IndexError:
        print('select the song with cursor')
        return
    song = song_box.get(previous_song)
    song_box.selection_clear(0, END)
    song_box.activate(previous_song)
    song_box.selection_set(previous_song, last=None)
    previous_pitch = audio.getPitch()
    loaded = False
    if not paused: play()
    try: music_slider.after_cancel(loop)
    except: pass

def forward():
    global song, song_box, music_slider, music_label_text, loaded, previous_pitch
    music_slider.config(value=0)
    music_label_text.set('00:00')
    try:
        next_song = (song_box.curselection()[0] + 1 ) % song_box.size()
    except IndexError:
        print('select the song with cursor')
        return
    song = song_box.get(next_song)
    song_box.selection_clear(0, END)
    song_box.activate(next_song)
    song_box.selection_set(next_song, last=None)
    previous_pitch = audio.getPitch()
    loaded = False
    if not paused: play()


def play():
    global paused, loaded, audio, song, music_slider
    if (not loaded) or (song != song_box.get(ACTIVE) ): #if it hasn't been loaded or the song changed
        stop()
        song = song_box.get(ACTIVE)
        song_index = song_box.index(ACTIVE)
        song_path = f'{playlists_record.get_directory(song)}{song}.mp3'
        loaded = True
        audio = PitchShifter(song_path, previous_pitch)
    #Play
    audio.play()
    paused = False
    update()
    #print(song)



def update():
    global loop, ani
    if paused: return
    if audio.Finish:
        forward()
        return
    current = time.strftime('%M:%S', time.gmtime( audio.getTime() ))
    music_label_text.set(current)
    music_slider.config(to= audio.DURATION, value = audio.getTime() )
    loop = music_slider.after(1000, update) #polls update continuously in separate thread

def pause():
    global paused
    audio.pause()
    paused= True

def stop():
    global audio
    try:
        audio.pause() #don't set pause since we just want to stop current audio
    except:
        pass



def pitch_slide(value):
    global pitch_slider, pitch_label_text, audio
    valuelist = [-12, -11, -10, -9, -8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    newvalue = min(valuelist, key=lambda x:abs(x-float(value)))
    pitch_slider.config(value=newvalue)
    pitch_label_text.set(newvalue)
    audio.setPitch(2**(newvalue/12))
    #print(2**(newvalue/12))
def music_slide(value):
    global music_label_text, audio
    seconds = int(float( music_slider.get() ))
    music_label_text.set( time.strftime('%M:%S', time.gmtime(seconds))  )
    audio.setTime(seconds)

def volume(event):
    global volume_slider
    print(volume_slider.get())



if __name__ == '__main__':
    root = Tk()
    root.config(bg="light blue")
    root.geometry("600x700")

    master_frame = Frame(root, bg="light blue")
    master_frame.pack(pady=20, padx=(30,0))
    ctrl_frame = Frame(root, width=60, bg="blue")
    ctrl_frame.place(relx=.5, rely=.5, anchor="center", x=-10, y=80)


    volume_frame = LabelFrame(master_frame, text="Volume", bg="grey")
    volume_frame.grid(row=1, column=2, padx=(20,0))

    song_box = Listbox(master_frame, bg = "black", fg="blue", width=50, selectbackground="white", selectforeground="black")
    song_box.grid(row=1, column=0, columnspan = 2)


    back_btn_img = PhotoImage(file='./images/back.png')
    forward_btn_img = PhotoImage(file='./images/forward.png')
    play_btn_img = PhotoImage(file='./images/play.png')
    pause_btn_img = PhotoImage(file='./images/pause.png')
    stop_btn_img = PhotoImage(file='./images/stop.png')
    return_btn_img = PhotoImage(file='./images/back_arrow.png')
    back_btn = Button(ctrl_frame, image=back_btn_img, borderwidth = 0, bg = "grey", activebackground = "grey", command=back)
    forward_btn = Button(ctrl_frame, image=forward_btn_img, borderwidth = 0, bg = "grey", activebackground = "grey", command=forward)
    play_btn = Button(ctrl_frame, image=play_btn_img, borderwidth = 0, bg = "grey", activebackground = "grey", command=play)
    pause_btn = Button(ctrl_frame, image=pause_btn_img, borderwidth = 0, bg = "grey", activebackground = "grey", command=pause)
    #stop_btn = Button(ctrl_frame, image=stop_btn_img, borderwidth = 0, bg = "grey", activebackground = "grey", command=stop)
    paused = True
    loaded = False

    back_btn.grid(row=1, column=0, pady=(20,0))
    forward_btn.grid(row=1, column=4, pady=(20,0))
    play_btn.grid(row=1, column=2, pady=(20,0))
    pause_btn.grid(row=1, column=1, pady=(20,0))
    #stop_btn.grid(row=1, column=3, pady=(20,0))


    my_menu = Menu(root)
    root.config(menu=my_menu)
    add_song_menu = Menu(my_menu, tearoff=0)
    my_menu.add_cascade(label = "Add Songs", menu=add_song_menu)
    add_song_menu.add_command(label="Add One Song To Menu", command=add_song)

    remove_song_menu = Menu(my_menu, tearoff=0)
    my_menu.add_cascade(label="Remove Songs", menu = remove_song_menu)
    remove_song_menu.add_command(label="Delete A Song From Menu", command = delete_song)


    pitch_slider = ttk.Scale(master_frame, from_=-12, to=12, orient=HORIZONTAL, value=0, command=pitch_slide, length = 360)
    pitch_slider.grid(row=3, column=0, pady=(30,10), columnspan = 2)
    pitch_slider.config(value=0)
    pitch_label_text = StringVar()
    pitch_label_text.set(0)
    pitch_label = ttk.Label(master_frame, textvariable =pitch_label_text)
    pitch_label = pitch_label.grid(row=3, column=2, pady=(30,10))

    # Create Music Position Slider my_slider
    music_label_text = StringVar()
    music_label_text.set('00:00')
    music_label = ttk.Label(master_frame, textvariable =music_label_text)
    music_label.grid(row=4, column=2, pady=(30,10))
    music_slider = ttk.Scale(master_frame, from_=0, to=300, orient=HORIZONTAL, value=0, length = 360) #command=music_slide
    music_slider.bind("<ButtonRelease-1>", music_slide)

    music_slider.grid(row=4, column=0, pady=(30,10), columnspan = 2)
    music_slider.config(value=0)

    # Create Volume Slider
    volume_slider = ttk.Scale(volume_frame, from_=0, to=1, orient=VERTICAL, value=0, command=volume, length = 111)
    volume_slider.pack(pady=(10, 4))
    volume_slider.config(value=1)

    label_title = StringVar()
    label_title.set('My Sick Playlist')
    info_label = Label(master_frame, textvariable=label_title, bg="grey")
    info_label.grid(row=0, column=1, sticky=W)


    fig = Figure(figsize = (5, 2),
                     dpi = 100)
    canvas = FigureCanvasTkAgg(fig, master = root)
    canvas.draw()
    canvas.get_tk_widget().place(relx=.5, rely=.5, anchor="center", x=-10, y=220)
    ax = fig.add_subplot(111)
    line, = ax.plot(range(1024), [0 for i in range(1024)])
    ax.set_ylim([-2,2])


    def plot(i):
       global fig, plot
       if not paused:
            #ax.magnitude_spectrum(audio.getData(), 48000)
            line.set_ydata(audio.getData())
            #canvas.draw()
            #canvas.flush_events()
            plt.show(block=False)

    ani = animation.FuncAnimation(fig, plot, interval=100, blit=False)
    plt.show(block=False)


    display_songs()
    root.mainloop()