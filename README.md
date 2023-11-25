# slack-async-meeting-manager (samm)

## Requirements
- nix


## Development

```bash
nix-shell
pipenv shell


# Shell 1
docker compose run -d mongo-server
docker compose run slack-app

# Shell 2
docker compose run mongo-client

```


## Attibutions

- Octopus Icon: <a href="https://www.flaticon.com/free-icons/octopus" title="octopus icons">Octopus icons created by Rohim - Flaticon</a>
