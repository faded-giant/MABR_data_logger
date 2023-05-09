while :
do
OXY_PORT=$(./test.sh | grep FT232  | head -n1 | awk '{print $1;}') 
ARD_PORT=$(./test.sh | grep Arduino  | head -n1 | awk '{print $1;}')
echo $(date): System started > system.log
echo Oxygen Sensor Port:  $OXY_PORT > system.log
echo Arduino Port:  $ARD_PORT  > system.log
sudo python3 ./modbus.py $OXY_PORT $ARD_PORT
done
