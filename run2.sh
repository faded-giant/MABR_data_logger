#!/bin/bash
cd ~/Desktop/ubuntu_logger
#while true; do
    OXY_PORT=$(./test.sh | grep FT232  | head -n1 | awk '{print $1;}')
    ARD_PORT=$(./test.sh | grep Arduino  | head -n1 | awk '{print $1;}')
    echo $(date): System started

    if [[ -n "$OXY_PORT" ]]; then
        echo Oxygen Sensor Port:  $OXY_PORT
    fi

    if [[ -n "$ARD_PORT" ]]; then
        echo Arduino Port:  $ARD_PORT
    fi

    controller_arg=""
    o2_arg=""

    if [[ -n "$ARD_PORT" ]]; then
        controller_arg="--controller_port $ARD_PORT"
    fi

    if [[ -n "$OXY_PORT" ]]; then
        o2_arg="--O2_port $OXY_PORT"
    fi

    sudo python3 ./logger.py $controller_arg $o2_arg

    # Wait for 5 seconds before the next iteration
    #sleep 5
#done
