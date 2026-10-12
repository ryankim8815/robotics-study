# -*- coding: utf-8 -*-
# =============================================================================
#  gripper_init.py - ROBOTIS RH-P12-RN(A) 그리퍼 초기화 Custom Code (개선판)
#
#  기존 초기화 코드(gripper_init_original.py)를 대신해 등록합니다.
#  함수 이름과 사용법은 같습니다: modbus_fc03/06/16(), recv_check(), gripper_move(stroke)
#  바뀐 점
#    1. 응답을 CRC 와 요청 내용까지 확인합니다. (이전: 바이트가 오기만 하면 성공)
#    2. 그리퍼가 응답하지 않으면 GRIPPER_INIT_RETRY 번 시도한 뒤 알람으로 멈춥니다. (이전: 무한 반복)
#    3. gripper_move() 가 응답을 읽어 확인합니다. 수신 버퍼에 응답이 남지 않고,
#       명령이 거부되거나 응답이 없으면 알람으로 멈춥니다. 명령 뒤 wait(1) 은 그대로입니다.
# =============================================================================

GRIPPER_SLAVE_ID     = 1
GRIPPER_BAUDRATE     = 57600
GRIPPER_GOAL_CURRENT = 400    # 잡는 힘: Goal Current [mA]
GRIPPER_INIT_RETRY   = 5      # 초기화 시도 횟수
GRIPPER_LOG_RAW      = False  # True: 응답 원문을 TP 로그로 출력 (이전 동작)

g_slaveid = 0
flag = 0


def modbus_set_slaveid(slaveid):
    global g_slaveid
    g_slaveid = slaveid


def modbus_fc03(startaddress, cnt):
    data = (g_slaveid).to_bytes(1, byteorder='big')
    data += (3).to_bytes(1, byteorder='big')
    data += (startaddress).to_bytes(2, byteorder='big')
    data += (cnt).to_bytes(2, byteorder='big')
    return modbus_send_make(data)


def modbus_fc06(address, value):
    data = (g_slaveid).to_bytes(1, byteorder='big')
    data += (6).to_bytes(1, byteorder='big')
    data += (address).to_bytes(2, byteorder='big')
    data += (value).to_bytes(2, byteorder='big')
    return modbus_send_make(data)


def modbus_fc16(startaddress, cnt, valuelist):
    data = (g_slaveid).to_bytes(1, byteorder='big')
    data += (16).to_bytes(1, byteorder='big')
    data += (startaddress).to_bytes(2, byteorder='big')
    data += (cnt).to_bytes(2, byteorder='big')
    data += (2 * cnt).to_bytes(1, byteorder='big')
    for i in range(0, cnt):
        data += (valuelist[i]).to_bytes(2, byteorder='big')
    return modbus_send_make(data)


def gripper_fail(msg):
    """오류를 TP 알람 팝업으로 알리고 프로그램을 멈춥니다."""
    tp_popup("[gripper] " + msg, DR_PM_ALARM, 1)
    exit()
    raise RuntimeError(msg)


def modbus_flush():
    """수신 버퍼에 남은 바이트를 버립니다."""
    for i in range(20):
        size, val = flange_serial_read(0.05)
        if size is None or size <= 0:
            return


def recv_check(expect_len=8):
    """응답 한 프레임을 읽고 CRC 를 확인합니다. 반환: (성공 여부, 데이터)

    플랜지 시리얼은 응답이 나뉘어 올 수 있어 expect_len 바이트가 모일 때까지 읽습니다.
    FC06 / FC16 응답은 8 byte, 예외 응답(기능 코드 + 0x80)은 5 byte 입니다.
    """
    buf = b""
    for i in range(10):
        size, val = flange_serial_read(0.1)
        if size is not None and size > 0:
            buf += val
        if len(buf) >= 5 and (buf[1] & 0x80):
            break
        if len(buf) >= expect_len:
            break
    if len(buf) >= 5 and (buf[1] & 0x80) and modbus_recv_check(buf[:5]):
        tp_log("Modbus exception: function {0}, code {1}".format(buf[1] & 0x7F, buf[2]))
        return False, buf
    if len(buf) >= expect_len and modbus_recv_check(buf[:expect_len]):
        if GRIPPER_LOG_RAW:
            tp_log(str(buf[:expect_len]))
        return True, buf[:expect_len]
    tp_log("Modbus response check fail ({0} bytes)".format(len(buf)))
    return False, buf


def modbus_request(frame, expect_len=8):
    """요청을 보내고 응답이 요청과 맞는지 확인합니다. (FC06/FC16 응답은 앞 6 byte 가 요청과 같음)"""
    modbus_flush()
    flange_serial_write(frame)
    ok, resp = recv_check(expect_len)
    return ok and resp[:6] == frame[:6]


def gripper_move(stroke):
    """Goal Position(282-283) 을 씁니다. 0 = 열림, 740 = 완전 닫힘."""
    for i in range(3):
        if modbus_request(modbus_fc16(282, 2, [stroke, 0])):
            wait(1)
            return
    gripper_fail("gripper_move({0}) was not acknowledged by the gripper.".format(stroke))


# ---- 초기화: 포트 열기 -> Torque Enable -> Goal Current ----------------------
#   256(40257) Torque Enable, 275(40276) Goal Current, 282(40283) Goal Position
for g_try in range(GRIPPER_INIT_RETRY):
    flange_serial_open(baudrate=GRIPPER_BAUDRATE, bytesize=DR_EIGHTBITS, parity=DR_PARITY_NONE,
                       stopbits=DR_STOPBITS_ONE)
    modbus_set_slaveid(GRIPPER_SLAVE_ID)
    flag = modbus_request(modbus_fc06(256, 1)) and modbus_request(modbus_fc06(275, GRIPPER_GOAL_CURRENT))
    if flag:
        break
    flange_serial_close()
    wait(0.5)

if not flag:
    gripper_fail("No response after {0} tries. Check cable, power, ID {1}, baudrate {2}.".format(
        GRIPPER_INIT_RETRY, GRIPPER_SLAVE_ID, GRIPPER_BAUDRATE))
