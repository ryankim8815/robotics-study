# 그리퍼 초기화 Custom Code 원본 (사용 중인 코드 원문 + gripper_move). 개선판은 gripper_init.py
# simulate.py --init gripper_init_original.py 로 원본 기준 동작도 검증할 수 있습니다.
g_slaveid = 0
flag=0

def modbus_set_slaveid(slaveid):
	global g_slaveid
	g_slaveid = slaveid

def modbus_fc03(startaddress, cnt):
	global g_slaveid
	data = (g_slaveid).to_bytes(1, byteorder='big')
	data += (3).to_bytes(1, byteorder='big')
	data += (startaddress).to_bytes(2, byteorder='big')
	data += (cnt).to_bytes(2, byteorder='big')

	return modbus_send_make(data)
def modbus_fc06(address, value):
	global g_slaveid
	data = (g_slaveid).to_bytes(1, byteorder='big')
	data += (6).to_bytes(1, byteorder='big')
	data += (address).to_bytes(2, byteorder='big')
	data += (value).to_bytes(2, byteorder='big')

	return modbus_send_make(data)

def modbus_fc16(startaddress, cnt, valuelist):
	global g_slaveid
	data = (g_slaveid).to_bytes(1, byteorder='big')
	data += (16).to_bytes(1, byteorder='big')
	data += (startaddress).to_bytes(2, byteorder='big')
	data += (cnt).to_bytes(2, byteorder='big')
	data += (2*cnt).to_bytes(1, byteorder='big')
	for i in range(0, cnt) :
		data += (valuelist[i]).to_bytes(2, byteorder='big')

	return modbus_send_make(data)


def recv_check() :
	size, val = flange_serial_read(0.1)

	if size > 0:
		tp_log(str(val))
		return True,val
	else:
		tp_log("CRC Check Fail")
		return False, val

while(True):
	flange_serial_open(baudrate=57600, bytesize=DR_EIGHTBITS, parity=DR_PARITY_NONE, stopbits = DR_STOPBITS_ONE)

	modbus_set_slaveid(1)

	#256(40257) Torque enable
	#282(40283) Goal Position
	#275(40276) Goal Current

	flange_serial_write(modbus_fc06(256,1))
	flag, val = recv_check()

	flange_serial_write(modbus_fc06(275,400))
	flag, val = recv_check()

	#flange_serial_write(modbus_fc16(282,2,[0,0]))
	#flag, val = recv_check()

	if flag == True :
		break

	flange_serial_close()


def gripper_move(stroke):
    flange_serial_write(modbus_fc16(282, 2, [stroke, 0]))
    wait(1)
