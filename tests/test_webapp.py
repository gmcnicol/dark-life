from typer.testing import CliRunner
from webapp.main import app, cli


def test_index_route():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200


def test_cli_run_command_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0
    assert "Run the Flask development server." in result.stdout
