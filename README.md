# What-is-the-plane bot

A telegram bot which tells you about the plane nearby


## Installation

1. Build a docker image with `./docker_build.sh`

2. Create `.env` file with contents `TELEGRAM_TOKEN=your telegram token`

3. Start the docker container: `docker-compose up -d`

You can also change the distance to check in `docker-compose.yml`


## Example

![Example of the bot message](/assets/example.png "Example of the bot message")
