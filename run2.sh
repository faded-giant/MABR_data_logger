#!/bin/bash
cd ~/Desktop/ubuntu_logger
#while true; do
    OXY_PORT=$(./get_port.sh | grep FT232  | head -n1 | awk '{print $1;}')
    ARD_PORT=$(./get_port.sh | grep Arduino  | head -n1 | awk '{print $1;}')
    SONDE_PORT=$(./get_port.sh | grep DSCJx11A920  | head -n1 | awk '{print $1;}')
    echo $(date): System started

    if [[ -n "$OXY_PORT" ]]; then
        echo Oxygen Sensor Port:  $OXY_PORT
    fi

    if [[ -n "$ARD_PORT" ]]; then
        echo Arduino Port:  $ARD_PORT
    fi

    if [[ -n "$SONDE_PORT" ]]; then
        echo Sonde Port:  $SONDE_PORT
    fi

    controller_arg=""
    o2_arg=""
    sonde_arg=""

    if [[ -n "$ARD_PORT" ]]; then
        controller_arg="--controller_port $ARD_PORT"
    fi

    if [[ -n "$OXY_PORT" ]]; then
        o2_arg="--O2_port $OXY_PORT"
    fi

    if [[ -n "$SONDE_PORT" ]]; then
        sonde_arg="--sonde_port $SONDE_PORT"
    fi

    sudo python3 ./logger.py $controller_arg $o2_arg $sonde_arg

    # Wait for 5 seconds before the next iteration
    #sleep 5
#done
