"""MasterForge visual studio — premium Studio Console desktop presentation.

The DSP, file dialogs, playback, reporting, launcher and build pipeline remain in
main.py / engine.py. This module overrides presentation only.
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from .main import MasterForgeWindow, PALETTES, AESTHETICS, FORMATS, LOUDNESS_CHOICES, mastering_defaults_description, fmt_time, VERSION


def blend(a: str, b: str, t: float) -> str:
    a = a.lstrip('#'); b = b.lstrip('#')
    return '#' + ''.join(f'{round(int(a[i:i+2],16)*(1-t)+int(b[i:i+2],16)*t):02x}' for i in (0,2,4))


def pill(canvas: tk.Canvas, x1, y1, x2, y2, radius, **kw):
    r = min(max(0, radius), (x2-x1)/2, (y2-y1)/2)
    coords = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r,
              x2,y2-r, x2,y2, x2-r,y2, x1+r,y2,
              x1,y2, x1,y2-r, x1,y1+r, x1,y1]
    return canvas.create_polygon(*coords, smooth=True, splinesteps=16, **kw)


class StudioButton(tk.Canvas):
    """Canvas-based button with rounded edges and tkinter-like configure API."""
    def __init__(self, parent, text, command, colors, *, primary=False, height=44,
                 radius=11, border=False, **kw):
        self.colors = colors
        self.text = text
        self.command = command
        self.primary = primary
        self.radius = radius
        self._state = 'normal'
        self.hover = False
        self.border = border
        bg = parent.cget('bg')
        super().__init__(parent, bg=bg, height=height, bd=0, highlightthickness=0,
                         cursor='hand2', takefocus=1, **kw)
        self.bind('<Configure>', self._draw)
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<Button-1>', lambda e: self._click())
        self.bind('<Return>', lambda e: self._click())
        self.bind('<space>', lambda e: self._click())

    def _enter(self, _):
        self.hover=True; self._draw()
    def _leave(self, _):
        self.hover=False; self._draw()
    def _click(self):
        if self._state == 'normal' and self.command:
            self.command()
    def configure(self, cnf=None, **kw):
        if 'text' in kw: self.text = kw.pop('text')
        if 'state' in kw: self._state = kw.pop('state')
        if 'command' in kw: self.command=kw.pop('command')
        if kw or cnf: super().configure(cnf, **kw)
        self._draw()
    config=configure

    def _draw(self, _=None):
        self.delete('all')
        w=max(2,self.winfo_width()); h=max(2,self.winfo_height())
        c=self.colors
        disabled=self._state!='normal'
        bg=c['accent'] if self.primary else c['panel2']
        if self.hover and not disabled:
            bg=blend(bg, c['wave'] if self.primary else c['text'], .12)
        if disabled: bg=blend(bg, c['panel'], .52)
        fg=c['bg'] if self.primary else c['text']
        if disabled: fg=c['muted']
        outline=c['line'] if (self.border or not self.primary) else bg
        pill(self,2,2,w-2,h-2,self.radius, fill=bg,outline=outline,width=1)
        family='Segoe UI' if os.name=='nt' else 'DejaVu Sans'
        self.create_text(w/2,h/2, text=self.text, font=(family,10,'bold'),fill=fg,
                         anchor='center',width=max(30,w-7))


class PresetCard(tk.Canvas):
    def __init__(self,parent,colors,title,description,icon,command,*,radius=12):
        self.colors=colors; self.title=title; self.description=description
        self.icon=icon; self.command=command; self.radius=radius
        self.selected=False; self.hover=False
        super().__init__(parent, bg=parent.cget('bg'),height=73,bd=0,highlightthickness=0,cursor='hand2')
        self.bind('<Configure>',self.draw)
        self.bind('<Enter>',lambda e:self._hover(True))
        self.bind('<Leave>',lambda e:self._hover(False))
        self.bind('<Button-1>',lambda e: self.command())
    def _hover(self,v):self.hover=v;self.draw()
    def set_selected(self,v):self.selected=v;self.draw()
    def draw(self,_=None):
        self.delete('all'); c=self.colors
        w=max(100,self.winfo_width()); h=max(50,self.winfo_height())
        bg=blend(c['panel2'],c['accent'],.095) if self.selected else c['panel2']
        if self.hover and not self.selected: bg=blend(bg,c['accent'],.07)
        border=c['accent'] if self.selected else c['line']
        pill(self,1,1,w-1,h-1,self.radius,fill=bg,outline=border,width=1.4 if self.selected else 1)
        if self.selected:
            pill(self,6,12,9,h-12,2,fill=c['accent'],outline=c['accent'])
        iconbg=blend(c['accent'],c['panel'],.7) if self.selected else blend(c['panel2'],c['text'],.08)
        pill(self,16,18,53,55,10,fill=iconbg,outline='')
        font='Segoe UI' if os.name=='nt' else 'DejaVu Sans'
        self.create_text(34,36,text=self.icon,fill=c['accent'] if self.selected else c['muted'],
                         font=(font,15,'bold'))
        self.create_text(67,26,text=self.title,fill=c['text'],font=(font,11,'bold'),anchor='w')
        self.create_text(67,46,text=self.description,fill=c['muted'],font=(font,9),anchor='w')
        self.create_oval(w-28,30,w-15,43,outline=c['accent'] if self.selected else c['muted'],width=1.4,
                         fill=c['accent'] if self.selected else bg)
        if self.selected: self.create_oval(w-24.8,33.2,w-18.2,39.8,outline='',fill=c['bg'])


class StudioSlider(tk.Canvas):
    def __init__(self,parent,var,min_value,max_value,colors,*,radius=8,value_label=None):
        self.variable=var;self.min=float(min_value);self.max=float(max_value);self.colors=colors
        self.value_label=value_label
        self._disabled=False
        super().__init__(parent,height=24,bg=parent.cget('bg'),highlightthickness=0,cursor='hand2')
        self.bind('<Configure>',self._draw)
        self.bind('<Button-1>',self._move)
        self.bind('<B1-Motion>',self._move)
        self._trace_id=self.variable.trace_add('write',self._changed)
    def _changed(self, *_):
        if self.value_label and self.value_label.winfo_exists():
            self.value_label.configure(text=f'{self.variable.get():+.1f}')
        if self.winfo_exists():
            self._draw()
    def destroy(self):
        try:
            self.variable.trace_remove('write',self._trace_id)
        except (tk.TclError,AttributeError):
            pass
        super().destroy()
    def state(self,flags):
        self._disabled='disabled' in flags
        if '!disabled' in flags:self._disabled=False
        self._draw()
    def _move(self,e):
        if self._disabled:return
        w=max(30,self.winfo_width())
        fraction=min(1,max(0,(e.x-11)/(w-22)))
        self.variable.set(self.min+fraction*(self.max-self.min))
    def _draw(self,_=None):
        self.delete('all');c=self.colors;w=max(30,self.winfo_width())
        t=min(1,max(0,(self.variable.get()-self.min)/(self.max-self.min)))
        x=11+(w-22)*t
        base=blend(c['line'],c['panel2'],.15)
        pill(self,10,10,w-10,14,2,fill=base,outline='')
        pill(self,10,10,max(11,x),14,2,fill=c['accent'],outline='')
        self.create_oval(x-7,5,x+7,19,fill=c['accent'],outline=c['panel'],width=2)
        self.create_oval(x-2,10,x+2,14,fill=c['bg'],outline='')


class TimelineScrubber(tk.Canvas):
    """Accessible, full-duration timeline with a large visible draggable playhead.

    Unlike ttk.Scale, Canvas renders consistently on KDE/CachyOS and Windows.
    The time range comes from the selected audio recording, never a fixed 100s.
    """
    def __init__(self,parent,colors,on_begin,on_preview,on_end):
        self.colors=colors
        self.duration=0.0
        self.position=0.0
        self.on_begin=on_begin
        self.on_preview=on_preview
        self.on_end=on_end
        self.dragging=False
        super().__init__(parent,height=39,bg=parent.cget('bg'),bd=0,
                         highlightthickness=0,cursor='hand2',takefocus=1)
        self.bind('<Configure>',self._draw)
        self.bind('<ButtonPress-1>',self._press)
        self.bind('<B1-Motion>',self._drag)
        self.bind('<ButtonRelease-1>',self._release)
        self.bind('<Left>',lambda e:self._keyboard_seek(-5))
        self.bind('<Right>',lambda e:self._keyboard_seek(5))
        self.bind('<Home>',lambda e:self._keyboard_to(0))
        self.bind('<End>',lambda e:self._keyboard_to(self.duration))

    def get(self):
        return self.position

    def set(self,value):
        self.position=min(self.duration,max(0.,float(value)))
        self._draw()

    def set_duration(self,seconds):
        self.duration=max(0.,float(seconds))
        self.position=min(self.position,self.duration)
        self._draw()

    def _value_at(self,x):
        width=max(1,self.winfo_width()-32)
        return self.duration*min(1.,max(0.,(x-16)/width))

    def _press(self,event):
        self.focus_set()
        if self.duration<=0:return
        self.dragging=True
        self.on_begin()
        self._update_pointer(event.x)

    def _update_pointer(self,x):
        self.set(self._value_at(x))
        self.on_preview(str(self.position))

    def _drag(self,event):
        if self.dragging:self._update_pointer(event.x)

    def _release(self,event):
        if not self.dragging:return
        self._update_pointer(event.x)
        self.dragging=False
        self.on_end()

    def _keyboard_to(self,position):
        if self.duration<=0:return 'break'
        self.on_begin()
        self.set(position)
        self.on_preview(str(self.position))
        self.on_end()
        return 'break'

    def _keyboard_seek(self,step):
        return self._keyboard_to(self.position+step)

    def _draw(self,_=None):
        self.delete('all');c=self.colors
        width=max(40,self.winfo_width());middle=19
        left,right=16,max(17,width-16)
        track=blend(c['line'],c['panel2'],.25)
        pill(self,left,middle-3,right,middle+3,3,fill=track,outline='')
        ratio=self.position/self.duration if self.duration>0 else 0.0
        x=left+(right-left)*min(1.,max(0.,ratio))
        if x>left:
            pill(self,left,middle-3,x,middle+3,3,fill=c['accent'],outline='')
        self.create_oval(x-10,middle-10,x+10,middle+10,
                         fill=c['accent'],outline=c['panel'],width=3)
        self.create_oval(x-3,middle-3,x+3,middle+3,fill=c['bg'],outline='')


class ThemeTile(tk.Canvas):
    def __init__(self,parent,name,palette,colors,selected,command):
        self.name=name;self.palette=palette;self.colors=colors;self.selected=selected;self.command=command
        super().__init__(parent, height=88,bg=parent.cget('bg'),bd=0,highlightthickness=0,cursor='hand2')
        self.bind('<Configure>',self.draw)
        self.bind('<Button-1>',lambda e:command())
        self.bind('<Enter>',lambda e:self.draw())
    def draw(self,_=None):
        self.delete('all');w=max(90,self.winfo_width());c=self.colors;p=self.palette
        pill(self,2,2,w-2,85,10,fill=c['panel2'],outline=c['accent'] if self.selected else c['line'],width=1.5)
        pill(self,9,8,w-9,49,7,fill=p['bg'],outline='')
        pill(self,16,15,49,41,5,fill=p['panel'],outline='')
        self.create_line(25,26,32,32,38,21,44,29,fill=p['wave'],width=2)
        pill(self,58,16,w-21,24,3,fill=p['line'],outline='')
        pill(self,58,30,max(65,w-55),38,3,fill=p['accent'],outline='')
        font='Segoe UI' if os.name=='nt' else 'DejaVu Sans'
        self.create_text(w/2,68,text=self.name,font=(font,9,'bold' if self.selected else 'normal'),fill=c['text'])


class LoudnessJourney(tk.Canvas):
    """Measured, never simulated, original-to-master loudness comparison."""
    def __init__(self,parent,colors):
        self.colors=colors
        self.original=None
        self.master_lufs=None
        self.target=None
        super().__init__(parent,height=88,bg=parent.cget('bg'),bd=0,highlightthickness=0)
        self.bind('<Configure>',self._draw)

    def update_values(self, original=None, master=None, target=None):
        self.original=original
        self.master_lufs=master
        self.target=target
        self._draw()

    def _draw(self,_=None):
        self.delete('all')
        c=self.colors;w=max(180,self.winfo_width());right=w-14;left=14
        font='Segoe UI' if os.name=='nt' else 'DejaVu Sans'
        self.create_text(left,9,text='LOUDNESS RANGE',anchor='nw',fill=c['muted'],font=(font,8,'bold'))
        self.create_text(right,9,text='MEASURED LUFS',anchor='ne',fill=c['muted'],font=(font,8,'bold'))
        start,end=left+2,right-2
        def x_for(v):return start+(end-start)*max(0,min(1,(v+28)/24))
        for i,tick in enumerate((-28,-22,-16,-10,-4)):
            x=x_for(tick)
            self.create_line(x,28,x,64,fill=blend(c['line'],c['panel2'],.3))
            self.create_text(x,76,text=str(tick),anchor='center',fill=c['muted'],font=(font,8))
        pill(self,start,45,end,50,3,fill=blend(c['line'],c['panel2'],.4),outline='')
        if self.original is not None:
            x=x_for(float(self.original))
            self.create_line(x,29,x,63,fill=c['muted'],width=2)
            self.create_oval(x-4,31,x+4,39,fill=c['muted'],outline='')
        if self.master_lufs is not None:
            x=x_for(float(self.master_lufs))
            self.create_line(x,28,x,63,fill=c['accent'],width=3)
            self.create_oval(x-5,40,x+5,50,fill=c['accent'],outline='')
            if self.original is not None:
                self.create_line(x_for(float(self.original)),47,x,47,fill=c['accent'],width=3)
        elif self.target is not None:
            x=x_for(float(self.target))
            self.create_line(x,33,x,60,fill=c['accent'],width=1,dash=(2,3))


class PolishedMasterForgeWindow(MasterForgeWindow):
    """Same feature/controller contract; rebuilt studio-console presentation only."""

    def _style(self):
        super()._style()
        c=self._colors(); s=ttk.Style(self.root)
        s.configure('Studio.Vertical.TScrollbar',background=c['panel2'],troughcolor=c['bg'],
                    arrowcolor=c['muted'],bordercolor=c['bg'],darkcolor=c['panel2'],lightcolor=c['panel2'],width=11)
        s.configure('Studio.Horizontal.TScale',background=c['panel'],troughcolor=c['line'])
        s.configure('Studio.TCombobox',padding=10,fieldbackground=c['panel2'],background=c['panel2'],
                    foreground=c['text'],arrowcolor=c['accent'],bordercolor=c['line'],
                    selectbackground=c['panel2'],selectforeground=c['text'])
        s.map('Studio.TCombobox',fieldbackground=[('readonly',c['panel2'])],
              foreground=[('readonly',c['text'])])

    def _font(self,sz=10,bold=False):
        return ('Segoe UI' if os.name=='nt' else 'DejaVu Sans',sz,'bold' if bold else 'normal')

    def _label(self,parent,text,size=11,bold=False,color='text',bg='panel',**kw):
        return super()._label(parent,text,size,bold,color,bg,**kw)

    def _panel(self,parent,pad=17,border=True):
        c=self._colors()
        # Elegant 1-pixel flat inset, independent of native OS widget styling.
        outline= c['line'] if self.aesthetic.get()!='Precision Minimalism' else blend(c['line'],c['panel'],.4)
        edge=tk.Frame(parent,bg=outline,padx=1,pady=1)
        inside=tk.Frame(edge,bg=c['panel'],padx=pad,pady=pad)
        inside.pack(fill='both',expand=True)
        return edge,inside

    def _head(self,parent,kicker,title):
        self._label(parent,kicker.upper(),9,True,'accent').pack(anchor='w',pady=(0,5))
        self._label(parent,title,15,True).pack(anchor='w',pady=(0,14))

    def _small_caption(self,parent,text):
        self._label(parent,text,9,color='muted',wraplength=260,justify='left').pack(anchor='w')

    def _action(self,parent,text,command,*,primary=False,height=44,border=False):
        aesthetic=self.aesthetic.get()
        radius=3 if aesthetic=='Analog Hardware' else 7 if aesthetic=='Precision Minimalism' else 12
        return StudioButton(parent,text,command,self._colors(),primary=primary,height=height,
                            border=border,radius=radius)

    def _build(self):
        # Changing a theme must not reset a loaded recording or playhead.
        previous_position = float(self.seek.get()) if hasattr(self, 'seek') else 0.0
        previous_scroll = self.body_canvas.yview()[0] if hasattr(self, 'body_canvas') else 0.0
        for child in self.root.winfo_children():child.destroy()
        self._style();c=self._colors()
        self.root.title('MasterForge AI  ·  Studio Console')
        if not getattr(self,'_visual_initialized',False):
            self.root.geometry('1480x950')
        self.root.minsize(1080,710)
        self._visual_initialized=True
        bar=tk.Frame(self.root,bg=c['panel'],padx=31,pady=15)
        bar.pack(fill='x')
        brand_icon=tk.Canvas(bar,width=48,height=48,bg=c['panel'],bd=0,highlightthickness=0)
        brand_icon.pack(side='left',padx=(0,13))
        pill(brand_icon,1,1,47,47,13,fill=blend(c['panel2'],c['accent'],.16),outline=c['line'])
        for x,amp in [(12,8),(18,15),(24,19),(30,12),(36,7)]:
            brand_icon.create_line(x,24-amp,x,24+amp,fill=c['accent'],width=2.5)
        btxt=tk.Frame(bar,bg=c['panel']);btxt.pack(side='left')
        name=tk.Frame(btxt,bg=c['panel']);name.pack(anchor='w')
        self._label(name,'MASTER',17,True,bg='panel').pack(side='left')
        self._label(name,'FORGE',17,True,'accent',bg='panel').pack(side='left')
        self._label(btxt,'STUDIO CONSOLE  /  DESKTOP MASTERING',8,True,'muted').pack(anchor='w',pady=(3,0))
        chip=tk.Frame(bar,bg=c['panel']);chip.pack(side='right')
        self.header_export=self._action(chip,'EXPORT MASTER  ↗',self.export_audio,primary=True,height=43)
        self.header_export.configure(width=181)
        self.header_export.pack(side='right')
        status_chip=tk.Frame(chip,bg=c['panel2'],padx=13,pady=12)
        status_chip.pack(side='right',padx=(0,17))
        self._label(status_chip,'●  ON-DEVICE AUDIO ENGINE',8,True,'accent',bg='panel2').pack()
        tk.Frame(self.root,bg=c['line'],height=1).pack(fill='x')

        # Fixed-width status footer; scrollable central workstation.
        statusbar=tk.Frame(self.root,bg=c['panel'],padx=29,pady=10)
        statusbar.pack(side='bottom',fill='x')
        self.status_label=self._label(statusbar,self.status,9,color='muted')
        self.status_label.pack(side='left')
        self.progress=ttk.Progressbar(statusbar,length=156,mode='indeterminate',style='Studio.Horizontal.TProgressbar')
        self.progress.pack(side='right');self.progress.pack_forget()
        self._label(statusbar,'SPACE  playback     CTRL+O  import     CTRL+S  export',8,color='muted').pack(side='right',padx=(0,24))

        self.body_canvas=tk.Canvas(self.root,bg=c['bg'],borderwidth=0,highlightthickness=0)
        sb=ttk.Scrollbar(self.root,command=self.body_canvas.yview,orient='vertical',style='Studio.Vertical.TScrollbar')
        sb.pack(side='right',fill='y')
        self.body_canvas.configure(yscrollcommand=sb.set)
        self.body_canvas.pack(fill='both',expand=True)
        inner=tk.Frame(self.body_canvas,bg=c['bg'],padx=28,pady=24)
        self.content_window=self.body_canvas.create_window((0,0),anchor='nw',window=inner)
        inner.bind('<Configure>',lambda e:self.body_canvas.configure(scrollregion=self.body_canvas.bbox('all')))
        self.body_canvas.bind('<Configure>',lambda e:self.body_canvas.itemconfigure(self.content_window,width=e.width))
        self.body_canvas.bind_all('<MouseWheel>',self._wheel)
        self.body_canvas.bind_all('<Button-4>',lambda e:self.body_canvas.yview_scroll(-2,'units'))
        self.body_canvas.bind_all('<Button-5>',lambda e:self.body_canvas.yview_scroll(2,'units'))

        hero=tk.Frame(inner,bg=c['panel'],padx=23,pady=19,highlightthickness=1,highlightbackground=c['line'])
        hero.pack(fill='x',pady=(0,20))
        accent_bar=tk.Frame(hero,bg=c['accent'],width=4);accent_bar.pack(side='left',fill='y',padx=(0,16))
        title_area=tk.Frame(hero,bg=c['panel']);title_area.pack(side='left',fill='x',expand=True)
        self._label(title_area,'WELCOME TO YOUR MASTERING WORKSPACE',8,True,'accent').pack(anchor='w',pady=(0,5))
        self._label(title_area,'Bring every detail forward.',22,True).pack(anchor='w')
        self._label(title_area,'Professional control, clear measurements, and your music kept local.',10,color='muted').pack(anchor='w',pady=(7,0))
        flow=tk.Frame(hero,bg=c['panel']);flow.pack(side='right',padx=(10,0))
        self.workflow_label=self._label(flow,'SESSION FLOW',8,True,'muted');self.workflow_label.pack(anchor='e',pady=(0,8))
        stages=tk.Frame(flow,bg=c['panel']);stages.pack(anchor='e')
        self.stage_tags=[]
        for index,name in enumerate(('IMPORT','SHAPE','MASTER','EXPORT')):
            color='accent' if index==0 else 'muted'
            background=blend(c['panel2'],c['accent'],.10) if index==0 else c['panel2']
            tile=tk.Frame(stages,bg=background,padx=9,pady=8,highlightthickness=1,highlightbackground=c['line'])
            tile.pack(side='left',padx=(0,5))
            lab=self._label(tile,f'{index+1:02d}  {name}',8,True,color,bg=background)
            lab.pack()
            self.stage_tags.append((tile,lab,index))

        main=tk.Frame(inner,bg=c['bg']);main.pack(fill='x')
        main.grid_columnconfigure(0,weight=26,uniform='main',minsize=258)
        main.grid_columnconfigure(1,weight=49,uniform='main',minsize=440)
        main.grid_columnconfigure(2,weight=25,uniform='main',minsize=270)
        self._left(main);self._center(main);self._right(main)
        self._themes(inner)
        foot=tk.Frame(inner,bg=c['bg']);foot.pack(fill='x',pady=(20,8))
        self._label(foot,'◈  YOUR SOUND. YOUR STUDIO. YOUR COMPUTER.',8,True,'muted',bg='bg').pack(side='left')
        self._label(foot,'STUDIO CONSOLE  ·  ENGINE v'+VERSION,8,color='muted',bg='bg').pack(side='right')
        self._update_track_ui()
        self._sync_waveform_view(position=previous_position)
        self._refresh_master_ui()
        if previous_scroll > 0.005:
            # Leave Theme Studio visible while trying color/aesthetic choices.
            # Deferred until tkinter has recomputed the scrollable content size.
            self.root.after(30, lambda v=previous_scroll: self.body_canvas.yview_moveto(v)
                            if self.body_canvas.winfo_exists() else None)

    def _left(self,parent):
        c=self._colors()
        column=tk.Frame(parent,bg=c['bg']);column.grid(row=0,column=0,sticky='nsew',padx=(0,8))
        edge,src=self._panel(column,15);edge.pack(fill='x',pady=(0,12))
        self._label(src,'01  /  SOURCE AUDIO',9,True,'accent').pack(anchor='w',pady=(0,11))
        drop=tk.Frame(src,bg=c['panel2'],padx=14,pady=16,
                      highlightthickness=1,highlightbackground=c['line'])
        drop.pack(fill='x')
        self._label(drop,'↑',24,True,'accent',bg='panel2').pack()
        self._label(drop,'Bring your track into the studio',10,True,bg='panel2').pack(pady=(4,2))
        self._label(drop,'WAV  ·  MP3  ·  FLAC  ·  M4A',8,color='muted',bg='panel2').pack(pady=(0,10))
        self.load_btn=self._action(drop,'+  OPEN AUDIO FILE',self.open_audio,primary=True,height=40)
        self.load_btn.pack(fill='x')
        self.source_line=self._label(src,'No file selected',9,color='muted',wraplength=260,justify='left')
        self.source_line.pack(anchor='w',pady=(11,0))

        edge,styles=self._panel(column,15);edge.pack(fill='x',pady=(0,12))
        self._label(styles,'02  /  SELECT ONE',9,True,'accent').pack(anchor='w',pady=(0,6))
        self._label(styles,'Mastering style',16,True).pack(anchor='w',pady=(0,12))
        presets={
           'natural':('Natural','Open, dynamic & authentic','∿'),
           'balanced':('Balanced','Clarity, polish & definition','≋'),
           'impact':('Impact','Bold, powerful & forward','ϟ'),
           'signature':('Signature   β','Dynamic tone & clarity','✧'),
        }
        self.preset_buttons={}
        for key,(title,detail,icon) in presets.items():
            card=PresetCard(styles,c,title,detail,icon,lambda k=key:self._choose_preset(k),
                            radius=4 if self.aesthetic.get()=='Analog Hardware' else 12)
            card.pack(fill='x',pady=(0,8))
            self.preset_buttons[key]=card
        self._highlight_preset()

        edge,tune=self._panel(column,16);edge.pack(fill='x')
        self._label(tune,'03  /  FINE TUNE',9,True,'accent').pack(anchor='w',pady=(0,12))
        self.sliders=[]
        for title,var,lo,hi,ends in [
            ('Warmth',self.warmth,-3,3,('LEAN','RICH')),
            ('Clarity',self.clarity,-3,3,('SMOOTH','CRISP')),
            ('Intensity',self.intensity,-2,2,('GENTLE','DRIVEN'))]:
            line=tk.Frame(tune,bg=c['panel']);line.pack(fill='x')
            self._label(line,title,10,True).pack(side='left')
            val=self._label(line,f'{var.get():+.1f}',10,True,'accent');val.pack(side='right')
            slider=StudioSlider(tune,var,lo,hi,c,value_label=val);slider.pack(fill='x',pady=(10,0))
            self.sliders.append(slider)
            labels=tk.Frame(tune,bg=c['panel']);labels.pack(fill='x',pady=(0,13))
            self._label(labels,ends[0],7,color='muted').pack(side='left')
            self._label(labels,ends[1],7,color='muted').pack(side='right')
        tk.Frame(tune,bg=c['line'],height=1).pack(fill='x',pady=(5,14))
        self._label(tune,'LOUDNESS INTENTION',9,True,'accent').pack(anchor='w',pady=(0,8))
        cb=ttk.Combobox(tune,textvariable=self.target,values=LOUDNESS_CHOICES,state='readonly',
                        style='Studio.TCombobox',width=24)
        cb.pack(fill='x',pady=(0,9))
        self._small_caption(tune,'Higher loudness may reduce dynamic range. Final output is measured after mastering.')
        tk.Frame(tune,bg=c['line'],height=1).pack(fill='x',pady=(17,14))
        self._label(tune,'YOUR STARTUP DEFAULTS',9,True,'accent').pack(anchor='w',pady=(0,7))
        self.saved_defaults_label=self._label(
            tune,mastering_defaults_description(self.startup_mastering),9,color='muted',
            wraplength=248,justify='left')
        self.saved_defaults_label.pack(anchor='w',pady=(0,10))
        self.save_defaults_button=self._action(tune,'★   SAVE CURRENT AS DEFAULT',self.save_mastering_defaults,
                          height=41,border=True)
        self.save_defaults_button.pack(fill='x',pady=(0,7))
        self.reset_defaults_button=self._action(tune,'↺   RESET STARTUP DEFAULTS',self.reset_mastering_defaults,
                           height=35)
        self.reset_defaults_button.pack(fill='x')

    def _center(self,parent):
        c=self._colors();col=tk.Frame(parent,bg=c['bg']);col.grid(row=0,column=1,sticky='nsew',padx=8)
        edge,ws=self._panel(col,20);edge.pack(fill='x',pady=(0,12))
        top=tk.Frame(ws,bg=c['panel']);top.pack(fill='x')
        self._label(top,'03  /  MASTERING WORKSPACE',9,True,'accent').pack(side='left')
        self.track_state=self._label(top,'●  MASTER READY' if self.master else '●  SOURCE READY' if self.source else '○  AWAITING AUDIO',8,True,'muted')
        self.track_state.pack(side='right')
        self.track_title=self._label(ws,'No track loaded',17,True,wraplength=560,justify='left')
        self.track_title.pack(anchor='w',pady=(15,3))
        self.track_detail=self._label(ws,'Import a song to begin your mastering session',9,color='muted',wraplength=550,justify='left')
        self.track_detail.pack(anchor='w',pady=(0,15))
        waveform_box=tk.Frame(ws,bg=blend(c['panel2'],c['bg'],.45),padx=1,pady=1,
                              highlightbackground=c['line'],highlightthickness=1)
        waveform_box.pack(fill='x')
        whead=tk.Frame(waveform_box,bg=blend(c['panel2'],c['bg'],.45),padx=12,pady=9)
        whead.pack(fill='x')
        self.wave_title=self._label(whead,'●  ORIGINAL WAVEFORM',8,True,'accent',bg=whead['bg'])
        self.wave_title.pack(side='left')
        self.wave_caption=self._label(whead,'00:00',8,True,'muted',bg=whead['bg']);self.wave_caption.pack(side='right')
        self.wave_canvas=tk.Canvas(waveform_box,height=245,bg=blend(c['panel2'],c['bg'],.55),highlightthickness=0)
        self.wave_canvas.pack(fill='x')
        self.wave_canvas.bind('<Configure>',lambda e:self._render_waveform())
        self.wave_canvas.bind('<Button-1>',self._seek_on_waveform)
        self.wave_canvas.configure(cursor='hand2')
        buttons=tk.Frame(ws,bg=c['panel']);buttons.pack(fill='x',pady=(15,8))
        self.play_button=self._action(buttons,'▶  PLAY',self.toggle_play,primary=True,height=43)
        self.play_button.configure(width=107);self.play_button.pack(side='left',padx=(0,8))
        self.stop_button=self._action(buttons,'■',self.stop_play,height=43)
        self.stop_button.configure(width=45);self.stop_button.pack(side='left')
        self.time_label=self._label(buttons,'00:00 / 00:00',10,True,'muted');self.time_label.pack(side='right')
        self.seek=TimelineScrubber(ws,c,self._begin_scrub,self._preview_scrub,self._end_scrub)
        self.seek.pack(fill='x',pady=(0,12))
        tk.Frame(ws,height=1,bg=c['line']).pack(fill='x',pady=(2,14))
        ab=tk.Frame(ws,bg=c['panel']);ab.pack(fill='x')
        self._label(ab,'COMPARE',9,True,'accent').pack(side='left',padx=(0,14))
        self.ab_widgets={}
        for choice in ('Original','Mastered'):
            button=self._action(ab,choice.upper(),lambda x=choice:self._select_ab(x),height=36)
            button.configure(width=117)
            button.pack(side='left',padx=(0,5))
            self.ab_widgets[choice]=button
        self._style_ab()
        self._check(ws,'Level-match A/B playback',self.level_match).pack(anchor='w',pady=(13,0))

        metric_edge,metric=self._panel(col,13);metric_edge.pack(fill='x',pady=(0,12))
        self._label(metric,'MEASURED AUDIO  /  PERFORMANCE MONITOR',9,True,'accent').pack(anchor='w',pady=(0,13))
        metr=tk.Frame(metric,bg=c['panel']);metr.pack(fill='x')
        vals=[('ORIGINAL LUFS','input_lufs'),('MASTER LUFS','output_lufs'),('TRUE PEAK','peak_metric')]
        for ix,(caption,attr) in enumerate(vals):
            tile=tk.Frame(metr,bg=c['panel2'],padx=12,pady=12)
            tile.pack(side='left',fill='both',expand=True,padx=(0,6 if ix<2 else 0))
            self._label(tile,caption,8,True,'muted',bg='panel2').pack(anchor='w')
            measure=self._label(tile,'—',17,True,bg='panel2');measure.pack(anchor='w',pady=(6,0))
            setattr(self,attr,measure)
        # The comparison visualization is driven only by measured audio values.
        self.loudness_plot=LoudnessJourney(metric,c)
        self.loudness_plot.pack(fill='x',pady=(15,1))
        self.stereo_line=self._label(metric,'STEREO CORRELATION   —',9,True,'muted')
        self.stereo_line.pack(anchor='w',pady=(14,0))
        self.peak_line=self._label(metric,'True peak: —',9,color='muted')
        # Kept as a state label: actual peak is also displayed in the third metric.
        self.peak_line.pack_forget()

        ed,assistant_box=self._panel(col,18);ed.pack(fill='x')
        self._label(assistant_box,'✦   MASTER ASSISTANT',9,True,'accent').pack(anchor='w',pady=(0,10))
        self.assistant=self._label(assistant_box,
            'Import a song to analyze its loudness and tonal profile. Then choose a finishing style and create a local 24-bit master.',
            10,color='text',wraplength=540,justify='left')
        self.assistant.pack(anchor='w')
        self._label(assistant_box,'◎  Your original is never overwritten.',9,color='muted').pack(anchor='w',pady=(12,0))

    def _right(self,parent):
        c=self._colors();column=tk.Frame(parent,bg=c['bg']);column.grid(row=0,column=2,sticky='nsew',padx=(8,0))
        edge,assistant=self._panel(column,17);edge.pack(fill='x',pady=(0,12))
        self._label(assistant,'✧  INTELLIGENT GUIDANCE',9,True,'accent').pack(anchor='w',pady=(0,9))
        self._label(assistant,'Shape. Measure. Deliver.',13,True).pack(anchor='w',pady=(0,9))
        self._small_caption(assistant,'Use Natural for openness, Balanced for versatility, Impact for energy, or Signature for dynamic response to changing sections.')
        self._label(assistant,'●  PRIVACY-FIRST LOCAL PROCESSING',8,True,'accent').pack(anchor='w',pady=(15,0))

        edge,output=self._panel(column,18);edge.pack(fill='x')
        self._head(output,'04 / Deliver','Export settings')
        self._label(output,'OUTPUT FORMAT',9,True,'accent').pack(anchor='w',pady=(0,9))
        self.format_buttons={}
        for fmt,detail in [('WAV','24-bit PCM · Lossless'),('MP3','Widely compatible'),('M4A','AAC · Efficient')]:
            row=tk.Frame(output,bg=c['panel2'],padx=7,pady=3,
                         highlightthickness=1,highlightbackground=c['line'])
            row.pack(fill='x',pady=(0,7))
            btn=self._action(row,fmt,lambda f=fmt:self._select_format(f),height=35)
            btn.configure(width=65)
            btn.pack(side='left',padx=(0,7))
            self._label(row,detail,9,color='muted',bg='panel2').pack(side='left')
            self.format_buttons[fmt]=btn
        self._style_format()
        br=tk.Frame(output,bg=c['panel']);br.pack(fill='x',pady=(11,7))
        self._label(br,'Bitrate',10,True).pack(side='left')
        self.bitrate_combo=ttk.Combobox(br,textvariable=self.bitrate,
                                       values=('128','192','256','320'),width=6,state='readonly',style='Studio.TCombobox')
        self.bitrate_combo.pack(side='right')
        self._small_caption(output,'Compressed exports are generated from the same WAV master. No remastering needed.')
        tk.Frame(output,bg=c['line'],height=1).pack(fill='x',pady=(19,16))
        self.master_btn=self._action(output,'✦   CREATE MASTER  →',self.make_master,primary=True,height=52)
        self.master_btn.pack(fill='x',pady=(0,9))
        self.export_btn=self._action(output,'↓   EXPORT AUDIO',self.export_audio,height=45)
        self.export_btn.pack(fill='x',pady=(0,9))
        self.report_btn=self._action(output,'↓   SAVE PROCESSING REPORT',self.save_report,height=43)
        self.report_btn.pack(fill='x')
        self._label(output,'Your music stays on this computer.',9,color='muted',wraplength=245,justify='left').pack(anchor='w',pady=(15,0))

    def _begin_scrub(self):
        self._seeking = True

    def _preview_scrub(self, value):
        self._seek_visual(value)
        self._update_playhead()

    def _end_scrub(self):
        self._seek_release(None)

    def _seek_on_waveform(self,event):
        """Click anywhere on the full-song waveform to jump to that point."""
        info = self._active_info()
        if not info or not hasattr(self, 'seek'):
            return
        width = max(20,self.wave_canvas.winfo_width()-16)
        portion = max(0.,min(1.,(event.x-8)/width))
        self._seeking = True
        self.seek.set(portion*float(info['duration']))
        self._seek_release(None)

    def _select_ab(self,choice):
        if choice=='Mastered' and not self.master:
            self.status='Create a master first to view its waveform'
            self.status_label.configure(text=self.status)
            return
        self.ab_mode.set(choice);self._style_ab();self._switch_ab()
    def _style_ab(self):
        if not hasattr(self,'ab_widgets'):return
        for name,btn in self.ab_widgets.items():
            btn.primary=(name==self.ab_mode.get())
            btn._draw()
    def _select_format(self,value):
        self.format.set(value);self._style_format();self._refresh_master_ui()
    def _style_format(self):
        if not hasattr(self,'format_buttons'):return
        for fmt,btn in self.format_buttons.items():
            btn.primary=(fmt==self.format.get());btn._draw()

    def _themes(self,inner):
        c=self._colors();edge,section=self._panel(inner,19)
        edge.pack(fill='x',pady=(20,0))
        head=tk.Frame(section,bg=c['panel']);head.pack(fill='x')
        self._label(head,'05  /  MAKE IT YOURS',9,True,'accent').pack(anchor='w',pady=(0,4))
        self._label(head,'Theme Studio',19,True).pack(anchor='w',pady=(0,5))
        self._label(head,'Six color palettes. Four interface aesthetics. Every combination is yours to explore.',
                    10,color='muted').pack(anchor='w',pady=(0,16))
        tiles=tk.Frame(section,bg=c['panel']);tiles.pack(fill='x')
        for i,(name,p) in enumerate(PALETTES.items()):
            tiles.grid_columnconfigure(i,weight=1,uniform='themes')
            tile=ThemeTile(tiles,name,p,c,name==self.palette.get(),lambda n=name:self.select_theme(n))
            tile.grid(row=0,column=i,sticky='nsew',padx=(0,8 if i<5 else 0))
        a=tk.Frame(section,bg=c['panel']);a.pack(fill='x',pady=(18,0))
        self._label(a,'INTERFACE AESTHETIC',9,True,'accent').pack(anchor='w',pady=(0,10))
        choices=tk.Frame(a,bg=c['panel']);choices.pack(fill='x')
        for n in AESTHETICS:
            btn=self._action(choices,n,lambda v=n:self.select_aesthetic(v),height=37)
            btn.primary=n==self.aesthetic.get()
            btn.pack(side='left',padx=(0,9))
            btn.configure(width={'Digital Studio':148,'Analog Hardware':158,'Precision Minimalism':190,'Hybrid':98}.get(n,125))
        restore=self._action(section,'↺  Restore original look',self.reset_theme,height=35)
        restore.configure(width=214)
        restore.pack(anchor='w',pady=(17,0))

    def _highlight_preset(self):
        for key,card in getattr(self,'preset_buttons',{}).items():
            if isinstance(card,PresetCard):card.set_selected(key==self.preset.get())
            else: super()._highlight_preset();break

    def _update_track_ui(self):
        super()._update_track_ui()
        c=self._colors()
        if hasattr(self,'loudness_plot'):
            input_lufs=(float(self.original_meter['input_i']) if self.original_meter else None)
            output_lufs=(float(self.report['output']['input_i']) if self.report else None)
            self.loudness_plot.update_values(original=input_lufs,master=output_lufs)
        self._update_stage_tags()
        if hasattr(self,'track_state'):
            self.track_state.configure(text='●  MASTER READY' if self.master else '●  SOURCE READY' if self.source else '○  AWAITING AUDIO')
        if hasattr(self,'source_line'):
            self.source_line.configure(text=f'♪  {self.source.name[:42]}' if self.source else 'No file selected')
        if self.report and hasattr(self,'peak_metric'):
            self.peak_metric.configure(text=f"{self.report['output']['input_tp']:+.1f} dBTP")
        if hasattr(self,'wave_caption'):
            info=self._active_info()
            active='MASTERED' if self.ab_mode.get()=='Mastered' and self.master else 'ORIGINAL'
            self.wave_caption.configure(text=f'FULL TRACK  ·  {fmt_time(info["duration"])}' if info else 'FULL TRACK  ·  00:00')
            if hasattr(self,'wave_title'):
                self.wave_title.configure(text=f'●  {active} WAVEFORM')

    def _update_stage_tags(self):
        if not hasattr(self,'stage_tags'):return
        c=self._colors()
        stage=2 if self.master else 1 if self.source else 0
        if self.busy:stage=max(1,stage)
        for tile,label,index in self.stage_tags:
            active=index<=stage
            bg=blend(c['panel2'],c['accent'],.10) if active else c['panel2']
            tile.configure(bg=bg,highlightbackground=c['accent'] if index==stage else c['line'])
            label.configure(bg=bg,fg=c['accent'] if active else c['muted'])

    def _refresh_master_ui(self):
        super()._refresh_master_ui()
        self._update_stage_tags()
        if hasattr(self,'header_export'):
            self.header_export.configure(state='normal' if self.master and not self.busy else 'disabled')

    def _render_waveform(self):
        if not hasattr(self,'wave_canvas') or not self.wave_canvas.winfo_exists():return
        canvas=self.wave_canvas;canvas.delete('all');c=self._colors()
        w=max(200,canvas.winfo_width());h=max(160,canvas.winfo_height());mid=h/2
        bg=canvas['bg']
        for i,y in enumerate((h*.18,mid,h*.82)):
            canvas.create_line(0,y,w,y,fill=blend(c['line'],bg,.18 if i==1 else .47),width=1)
        # A soft center band acts as a visual anchor without normalizing either signal.
        canvas.create_rectangle(0,mid-21,w,mid+21,fill=blend(bg,c['wave'],.027),outline='')
        canvas.create_line(0,mid,w,mid,fill=blend(c['line'],c['wave'],.12),width=1)
        for x in range(0,w,70):
            canvas.create_line(x,0,x,h,fill=blend(c['line'],bg,.53),width=1)
        if not self.waveform:
            canvas.create_text(w/2,mid-8,text='YOUR WAVEFORM WILL APPEAR HERE',
                               font=self._font(10,True),fill=c['muted'])
            canvas.create_text(w/2,mid+16,text='Load an audio file to see the signal',
                               font=self._font(9),fill=c['muted'])
            return
        # Fit the entire recording to the canvas. When resized smaller, merge
        # neighboring time bins by their maximum peak (never discard samples).
        arr = self.waveform
        # Both tracks use the *same* amplitude scale. Independent normalization
        # made different dynamics appear nearly identical before this update.
        comparison = self.original_waveform + self.master_waveform
        shared_scale = max(0.035, max(comparison, default=1.0))
        margin = 8
        plot_width = max(1, w - 2 * margin)
        columns = max(1, min(len(arr), int(plot_width / 3)))
        for i in range(columns):
            first = int(i * len(arr) / columns)
            last = max(first + 1, int((i + 1) * len(arr) / columns))
            amplitude = max(arr[first:last], default=0.0)
            x = margin + plot_width * (i + .5) / columns
            amp = max(1.0, min(1.0, max(0.0, float(amplitude)) / shared_scale) * (h * .405))
            color = c['accent'] if self.ab_mode.get()=='Mastered' and self.master else c['wave']
            thickness=max(1.0, min(2.6, .75 * plot_width / columns))
            canvas.create_line(x,mid-amp, x,mid+amp,fill=blend(color,bg,.67),width=thickness+2.7)
            canvas.create_line(x,mid-amp, x,mid+amp,fill=color,width=thickness)
        # The time ruler spans 0:00 to the actual end of the file.
        info = self._active_info()
        duration = float(info['duration']) if info else 0.0
        for i in range(5):
            x = margin + plot_width * i / 4
            anchor = 'w' if i == 0 else ('e' if i == 4 else 'center')
            canvas.create_text(x, h - 10, text=fmt_time(duration * i / 4),
                               font=self._font(8), fill=c['muted'], anchor=anchor)
        if info and hasattr(self,'seek'):
            current=float(self.seek.get());duration=max(.01,duration)
            x=min(w-margin,max(margin,margin+(current/duration)*plot_width))
            canvas.create_line(x,0,x,h-22,fill=c['accent'],width=2,tags=('playhead',))
            canvas.create_polygon(x-6,0,x+6,0,x,7,fill=c['accent'],outline='')
