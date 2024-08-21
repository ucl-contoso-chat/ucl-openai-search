from pathlib import Path
from unittest.mock import patch

import matplotlib.pyplot as plt

from evaluation.plotting import (
    plot_bar_charts,
    plot_box_chart,
    plot_box_charts_grid,
    plot_radar_chart,
)


@patch("matplotlib.pyplot.savefig")
def test_plot_bar_charts(mock_savefig):
    """Test plot_bar_charts function."""

    layout = (1, 2)  # 1 row, 2 columns -> 2 subplots

    # Simplified data to avoid array issues
    data = {
        "Model A": [{"Category 1": 1}, {"Category 1": 3}],
        "Model B": [{"Category 1": 2}, {"Category 1": 4}],
    }
    titles = ["Chart 1", "Chart 2"]  # Adjusted to match the number of subplots
    y_labels = ["Y Label 1", "Y Label 2"]  # Adjusted to match the number of subplots

    output_path = Path("test_bar_chart.png")
    plot_bar_charts(layout, data, titles, y_labels, output_path=output_path)

    mock_savefig.assert_called_once_with(output_path, bbox_inches="tight", format="png")
    plt.close("all")


@patch("matplotlib.pyplot.savefig")
def test_plot_multiple_box_charts(mock_savefig):
    """Test plot_multiple_box_charts function."""

    layout = (1, 2)
    data = {
        "Metric 1": [[1, 2, 3], [4, 5, 6]],
        "Metric 2": [[2, 3, 4], [5, 6, 7]],
    }
    titles = ["Box Chart 1", "Box Chart 2"]
    y_labels = ["Y Label 1", "Y Label 2"]

    output_path = Path("test_multiple_box_charts.png")
    plot_box_charts_grid(layout, data, titles, y_labels, output_path=output_path)

    mock_savefig.assert_called_once_with(output_path, bbox_inches="tight", format="png")
    plt.close("all")


@patch("matplotlib.pyplot.savefig")
def test_plot_single_box_chart(mock_savefig):
    """Test plot_single_box_chart function."""

    data = {
        "Metric A": [[1, 2, 3], [4, 5, 6]],
        "Metric B": [[2, 3, 4], [5, 6, 7]],
    }
    title = "Single Box Chart"
    x_labels = ["Label 1", "Label 2"]
    y_label = "Y Label"

    output_path = Path("test_single_box_chart.png")
    plot_box_chart(data, title, x_labels, y_label, output_path=output_path)

    mock_savefig.assert_called_once_with(output_path, bbox_inches="tight", format="png")
    plt.close("all")


@patch("matplotlib.pyplot.savefig")
def test_plot_radar_chart(mock_savefig):
    """Test plot_radar_chart function."""

    metric_label_list = ["Metric 1", "Metric 2", "Metric 3"]
    data = {
        "Model X": [0.2, 0.4, 0.6],
        "Model Y": [0.5, 0.7, 0.9],
    }
    title = "Radar Chart"
    num = 5

    output_path = Path("test_radar_chart.png")
    plot_radar_chart(metric_label_list, data, title, output_path, num)

    mock_savefig.assert_called_once_with(output_path, bbox_inches="tight", format="png")
    plt.close("all")
