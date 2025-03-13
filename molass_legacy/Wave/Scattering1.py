"""
    Wave.Scattering.py

    Copyright (c) 2020, SAXS Team, KEK-PF
"""
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.animation as animation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from OurTkinter import Tk, Dialog
from OurMatplotlib import NavigationToolbar

class BeamAnimDialog(Dialog):
    def __init__(self, parent):
        Dialog.__init__(self, parent, "Beam Animatio", visible=False)

    def show(self):
        self._show()

    def body(self, body_frame):
        cframe = Tk.Frame(body_frame)
        cframe.pack()
        bframe = Tk.Frame(body_frame)
        bframe.pack(fill=Tk.BOTH, expand=1)
        tframe = Tk.Frame(bframe)
        tframe.pack(side=Tk.LEFT)
        pframe = Tk.Frame(bframe)
        pframe.pack(side=Tk.RIGHT)

        fig, axes = plt.subplots(ncols=2, figsize=(14, 7))
        self.fig  = fig
        self.mpl_canvas = FigureCanvasTkAgg(fig, cframe)
        self.mpl_canvas_widget = self.mpl_canvas.get_tk_widget()
        self.mpl_canvas_widget.pack(fill=Tk.BOTH, expand=1)
        self.toolbar = NavigationToolbar(self.mpl_canvas, tframe)
        self.toolbar.update()
        self.draw_anim(fig, axes)
        self.mpl_canvas.draw()

    def draw_anim(self, fig, axes):
        ax1, ax2 = axes

        for ax in axes:
            ax.grid(False)

        N = 800
        n = N//2
        r = np.arange(N)
        rr = r**2
        i = np.arange(N)
        ii, jj = np.meshgrid(i, i)
        labels = np.searchsorted(rr, (ii - n)**2 + (jj-n)**2)
        Lmax = np.max(labels)

        canvas = np.zeros((N, N))
        x = np.linspace(0, np.pi*96, N+Lmax)

        def color_filter(v):
            return 1/(1 + np.exp(-2*(v - 1.999)))

        cmap = 'plasma'
        target_particle = labels <= 5

        def animate_func(i):
            t = np.pi*i/2
            beam = color_filter(1 + np.sin(x[0:n] - t))
            canvas[n-2:n+3,0:n] = beam      # as if linewith=5
            canvas[target_particle] = 1
            im1 = ax1.imshow(canvas, animated=True, cmap=cmap, origin='lower')
            scattered = color_filter(1 + np.sin(x[n:] - t))
            im2 = ax2.imshow(scattered[labels], animated=True, cmap=cmap, origin='lower')
            return [im1, im2]

        fig.tight_layout()
        self.ani = animation.FuncAnimation(fig, animate_func, frames=60, interval=50, blit=True)
        # self.ani.save('scattering.mp4', writer="ffmpeg")

def demo1():
    from TkUtils import get_tk_root

    root = get_tk_root()

    def show_demo():
        dialog = BeamAnimDialog(root)
        dialog.show()
        root.quit()

    root.after(100, show_demo)
    root.mainloop()
    root.destroy()
