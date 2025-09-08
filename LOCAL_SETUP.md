## LOCAL SETUP

### Prerequisites
- Docker (https://docs.docker.com/get-docker/)
- Get the following keys from Yason
   - `OPENAI_API_KEY`
   - `TAVILY_API_KEY`
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

### Setup Instructions

1. Clone repo
   For SSH:
   ```shell
   git clone git@github.com:breba-apps/disc-site.git
   ```
   For HTTPS:
   ```shell
   git clone https://github.com/breba-apps/disc-site.git
   ```
   
2. Run the stet up script
   ```shell
   cd disc-site
   ./scripts/dev-setup-scripts
   ```
