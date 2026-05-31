# BeSeenDoorController
Code to interact with BeSeenControl Door Controller via web interface

Code Runs in a Docker container and uses compose and a local config file to store configuartion information.

To Pull Swipes from a door controller:

docker compose run doorcontroller get_swipes
docker compose run doorcontroller get_acl_from_controller
docker compose run doorcontroller get_foblist_from_controller


Running get_swipes from cron (every 15 minutes)

*/15 * * * * cd /opt/scripts/BeSeenDoorController && docker compose -f docker-compose.yaml run doorcontroller get_swipes > /dev/null 2>&1



