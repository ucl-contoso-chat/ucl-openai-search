from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.patches import RegularPolygon
from matplotlib.path import Path as MatPath
from matplotlib.projections import register_projection
from matplotlib.projections.polar import PolarAxes
from matplotlib.spines import Spine
from matplotlib.transforms import Affine2D


def plot_bar_charts(
    layout: Tuple[int, int],
    data: Dict[str, List[Dict[str, any]]],
    titles: List[str],
    y_labels: List[str],
    y_max_lim: List[float] = None,
    width=0.4,
    output_path: Path = Path("evaluation_results.png"),
):
    """Plot bar charts for the provided data."""
    if layout[0] * layout[1] != len(data):
        raise ValueError("Number of data points must match the layout")

    font = {"weight": "normal", "size": 9}

    matplotlib.rc("font", **font)

    fig, axs = plt.subplots(layout[0], layout[1], figsize=(layout[1] * 5, layout[0] * 4))
    fig.tight_layout(pad=3.0)

    if axs is not np.ndarray:
        axs = np.array([axs])

    for i, ax in enumerate(axs.flat):
        ax = axs.flat[i]
        category_labels = []
        y_data = []
        for key, categories in data.items():
            category_labels.append(key)
            all_x_data = set()
            for category in categories:
                all_x_data.update(category.keys())
            all_x_data = sorted(list(all_x_data))
            x_base = list(range(len(all_x_data)))
            bar_width = 0.25
            offsets = [-bar_width, 0, bar_width]
            category_positions = [[x + offset for x in x_base] for offset in offsets]
            bar_width = width / len(categories)
            y_data_per_model = list(categories[i].values())
            y_data.append(y_data_per_model)

        colors = plt.cm.tab20.colors
        for pos_list, height, color, label in zip(category_positions, y_data, colors, category_labels):
            bars = ax.bar(pos_list, height, width=bar_width, color=color, label=label)
            for bar in bars:
                yval = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2, yval, round(yval, 1), ha="center", va="bottom", fontsize=8)

        if y_max_lim is not None and len(y_max_lim) > i and y_max_lim[i] is not None:
            ax.set_ylim(0, y_max_lim[i] * 1.5)
        else:
            ax.set_ylim(0, np.ceil(max(y_data)) * 1.2)

        ax.set_title(titles[i], pad=20)
        ax.set_ylabel(y_labels[i])
        ax.set_xticks(x_base)
        ax.set_xticklabels(all_x_data)
        ax.legend()

    plt.savefig(output_path)
    plt.close(fig)


def plot_multiple_box_charts(
    layout: Tuple[int, int],
    data: Dict[str, List[List[float]]],
    titles: List[str],
    y_labels: List[str],
    output_path: Path,
):
    """Plot box charts for the provided data."""
    if layout[0] * layout[1] != len(data):
        raise ValueError("Number of plots must match the layout")

    fig, axs = plt.subplots(layout[0], layout[1], figsize=(layout[1] * 5, layout[0] * 4))
    fig.tight_layout(pad=3.0)

    if not isinstance(axs, np.ndarray):
        axs = np.array([axs])

    positions = range(0, len(data.keys()))
    offset = 0.2

    for i, ax in enumerate(axs.flat):
        current_positions = []
        ax = axs.flat[i]
        for j, (key, values) in enumerate(data.items()):
            current_positions = [j + offset]
            ax.boxplot(
                values[i],
                positions=current_positions,
                boxprops=dict(color=f"C{j}"),
                medianprops=dict(color="red"),
                whiskerprops=dict(color=f"C{j}"),
                capprops=dict(color=f"C{j}"),
            )
            ax.plot([], [], color=f"C{j}", label=key)
        ax.legend()
        ax.set_title(titles[i])
        ax.set_ylabel(y_labels[i])
        ax.set_xticks(positions)
        ax.set_xticklabels(data.keys())

    plt.savefig(output_path)
    plt.close(fig)


def plot_single_box_chart(
    data: Dict[str, List[List[float]]],
    title: str,
    x_labels: List[str],
    y_label: str,
    y_lim: Tuple[float, float] = None,
    output_path: Path = Path("boxplot.png"),
):
    """Plot a box chart for the provided data."""

    plt.figure(figsize=(10, 6))

    positions = range(1, len(x_labels) + 1)

    offset = 0.2
    box_positions = []

    for i, (key, values) in enumerate(data.items()):
        current_positions = []
        for p in positions:
            current_positions.append(p + i * offset - (offset * (len(data) - 1) / 2))
        box_positions.append(current_positions)

        plt.boxplot(
            values,
            positions=current_positions,
            widths=0.15,
            patch_artist=True,
            boxprops=dict(color=f"C{i}", facecolor="none"),
            medianprops=dict(color="red"),
            whiskerprops=dict(color=f"C{i}"),
            capprops=dict(color=f"C{i}"),
            flierprops=dict(marker="o", color=f"C{i}", alpha=0.5),
        )
        plt.plot([], [], color=f"C{i}", label=key)
    plt.legend()
    plt.title(title)
    plt.ylabel(y_label)
    plt.xticks(positions, x_labels)

    if y_lim:
        plt.ylim(y_lim)

    plt.savefig(output_path)
    plt.close()


def plot_radar_chart(metric_label_list: List[str], data: Dict[str, List], title: str, output_path: Path, num: int):
    theta = radar_factory(num_vars=len(metric_label_list))
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(projection="radar"))
    fig.subplots_adjust(wspace=0.5, hspace=0.20, top=0.85, bottom=0.05)

    colors = ["b", "r", "g", "m", "c", "y"]

    ax.set_title(title, weight="bold", size="large", horizontalalignment="center", verticalalignment="center", pad=20)

    for idx, (label, data) in enumerate(data.items()):
        color = colors[idx % len(colors)]
        ax.plot(theta, data, color=color, label=label)
        ax.fill(theta, data, facecolor=color, alpha=0.25)
    ax.legend(loc="upper right", bbox_to_anchor=(1.1, 1.1))
    ax.tick_params(pad=15)
    r_values = np.linspace(0, num, num + 1)
    ax.set_rgrids(r_values, angle=10)
    # ax.set_rgrids([0, 1, 2, 3, 4, 5], angle=10)
    ax.set_varlabels(metric_label_list)

    plt.savefig(output_path)
    plt.close(fig)


def radar_factory(num_vars):
    """
    Create a radar chart with `num_vars` Axes.
    This function creates a RadarAxes projection and registers it.

    Parameters
    ----------
    num_vars : int
        Number of variables for radar chart.
    """
    # calculate evenly-spaced axis angles
    theta = np.linspace(0, 2 * np.pi, num_vars, endpoint=False)

    class RadarTransform(PolarAxes.PolarTransform):

        def transform_path_non_affine(self, path):
            # Paths with non-unit interpolation steps correspond to gridlines,
            # in which case we force interpolation (to defeat PolarTransform's
            # autoconversion to circular arcs).
            if path._interpolation_steps > 1:
                path = path.interpolated(num_vars)
            return MatPath(self.transform(path.vertices), path.codes)

    class RadarAxes(PolarAxes):

        name = "radar"
        PolarTransform = RadarTransform

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # rotate plot such that the first axis is at the top
            self.set_theta_zero_location("N")

        def fill(self, *args, closed=True, **kwargs):
            """Override fill so that line is closed by default"""
            return super().fill(closed=closed, *args, **kwargs)

        def plot(self, *args, **kwargs):
            """Override plot so that line is closed by default"""
            lines = super().plot(*args, **kwargs)
            for line in lines:
                self._close_line(line)

        def _close_line(self, line):
            x, y = line.get_data()
            # FIXME: markers at x[0], y[0] get doubled-up
            if x[0] != x[-1]:
                x = np.append(x, x[0])
                y = np.append(y, y[0])
                line.set_data(x, y)

        def set_varlabels(self, labels):
            self.set_thetagrids(np.degrees(theta), labels)
            self.xaxis.set_tick_params(pad=15)

        def _gen_axes_patch(self):
            # The Axes patch must be centered at (0.5, 0.5) and of radius 0.5
            # in axes coordinates.
            return RegularPolygon((0.5, 0.5), num_vars, radius=0.5, edgecolor="k")

        def _gen_axes_spines(self):
            # spine_type must be 'left'/'right'/'top'/'bottom'/'circle'.
            spine = Spine(axes=self, spine_type="circle", path=MatPath.unit_regular_polygon(num_vars))
            # unit_regular_polygon gives a polygon of radius 1 centered at
            # (0, 0) but we want a polygon of radius 0.5 centered at (0.5,
            # 0.5) in axes coordinates.
            spine.set_transform(Affine2D().scale(0.5).translate(0.5, 0.5) + self.transAxes)
            return {"polar": spine}

    register_projection(RadarAxes)
    return theta
