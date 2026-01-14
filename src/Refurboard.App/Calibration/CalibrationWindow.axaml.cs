using System;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Interactivity;
using Avalonia.Markup.Xaml;

namespace Refurboard.App.Calibration;

public partial class CalibrationWindow : Window
{
    private readonly CalibrationViewModel _viewModel;

    public CalibrationWindow()
    {
        InitializeComponent();
        _viewModel = new CalibrationViewModel();
        _viewModel.Completed += OnCompleted;
        DataContext = _viewModel;
    }

    private void OnPointerPressed(object? sender, PointerPressedEventArgs e)
    {
        if (e.Source is Button)
        {
            return;
        }

        var position = e.GetPosition(this);
        _viewModel.RecordPoint(position, Bounds.Size);
    }

    private void OnCompleted(object? sender, EventArgs e)
    {
        Close(_viewModel.ToOutcome(Bounds.Size));
    }

    private void OnCancelClicked(object? sender, RoutedEventArgs e)
    {
        Close(null);
    }

    private void OnKeyDownHandler(object? sender, KeyEventArgs e)
    {
        if (e.Key == Key.Escape)
        {
            Close(null);
        }
    }
}
