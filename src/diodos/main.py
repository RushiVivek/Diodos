import typer

from .commands import daemon, login, logout, config, start, stop

app = typer.Typer(invoke_without_command=True, no_args_is_help=True)
context_settings = dict(help_option_names=["-h", "--help"])

@app.callback(context_settings=context_settings)
def callback(
    version: bool = typer.Option(
        False,
        "--version",
        is_eager=True,
        help="Show the application version and exit.",
    ),
) -> None:
    """
    Diodos is a command-line tool that helps you automatically log in to captive portals on saved Wi-Fi networks. It monitors network connections and detects when a captive portal is present, allowing you to seamlessly authenticate without manual intervention.
    """
    if version:
        from diodos import __version__
        typer.echo(f"Diodos version {__version__}")
        raise typer.Exit()

app.command("start")(start.main)
app.command("stop")(stop.main)
app.command("daemon")(daemon.main)
app.command("login")(login.main)
app.command("logout")(logout.main)
app.command("config")(config.main)
