# How to use this template

1. Install `uv` using `winget install Astral.uv` or `brew install uv` or `pipx install uv`. Check their [installation guide](https://docs.astral.sh/uv/getting-started/installation/) for more.

2. Clone this repository and navigate into the project directory:

```bash
git clone ...
cd template-dspy-redis...
```

3. Update the project name and other relevant details in `pyproject.toml`. Rename all instances of `rename_me` to your desired module name.

4. Grab the dependencies using `uv sync`.

5. Copy the provided `example.env` file to `.env` and set any environment variables your project may need. Do not push `.env` to version control. Instead, add example values to `example.env` to share with collaborators.

6. Add your favorite dependencies using `uv add <package-name>`.

7. Run the project using `uv run -m rename_me.main` or `uv run main`. The latter works because we set up an alias in `pyproject.toml` under `[project.scripts]`.

8. Change this file to describe your project!
