"""Shared Typer app construction helpers."""

import typer


def build_typer_app(
    *,
    name: str,
    help_text: str,
    allow_interspersed_args: bool = False,
) -> typer.Typer:
    """Create a Typer app with WKS-standard configuration."""
    context_settings: dict[str, object] = {"help_option_names": ["-h", "--help"]}
    if allow_interspersed_args:
        context_settings["allow_interspersed_args"] = True

    return typer.Typer(
        name=name,
        help=help_text,
        pretty_exceptions_show_locals=False,
        pretty_exceptions_enable=False,
        context_settings=context_settings,
        invoke_without_command=True,
    )


def require_subcommand(app: typer.Typer, *, err: bool = True) -> None:
    """Attach the standard help-and-exit callback for subcommand-only apps."""

    @app.callback(invoke_without_command=True)
    def callback(ctx: typer.Context) -> None:
        if ctx.invoked_subcommand is None:
            typer.echo(ctx.get_help(), err=err)
            raise typer.Exit(2)
