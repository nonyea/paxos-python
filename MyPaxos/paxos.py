#!/usr/bin/env python3
import sys
import socket
import struct
import pickle
import math
import time
import threading
import os
import numpy as np
from message import Message
from config import Acceptors_num as Acceptors_num
from config import Loss as Loss
from config import Timeout as Timeout




def mcast_receiver(hostport):
    """create a multicast socket listening to the address"""
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    recv_sock.bind(hostport)

    mcast_group = struct.pack("4sl", socket.inet_aton(hostport[0]), socket.INADDR_ANY)
    recv_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mcast_group)
    return recv_sock


def mcast_sender():
    """create a udp socket"""
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    return send_sock


def parse_cfg(cfgpath):
    cfg = {}
    with open(cfgpath, 'r') as cfgfile:
        for line in cfgfile:
            (role, host, port) = line.split()
            cfg[role] = (host, int(port))
    return cfg

# ----------------------------------------------------

def acceptor(config, id):
    #print('-> acceptor', id)
    print('-> acceptor', id, ' id:', os.getpid())
    #state = {}
    r = mcast_receiver(config['acceptors'])
    s_acceptor = mcast_sender()
    state_acceptor = dict()

    while True:
        msg = None
        msg = r.recv(2 ** 16)
        if msg is not None:
            msg_decoded = Message(0, 'DECODING').decode(msg)
            current_instance = msg_decoded.instance
            current_phase = msg_decoded.phase

            if current_phase == '1A':
                if current_instance not in state_acceptor.keys():
                    state_acceptor[current_instance] = {
                        'rnd': msg_decoded.c_rnd,
                        'v_rnd': 0,
                        'v_val': None,
                    }
                    if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                        msg_phase_1B = Message(current_instance, '1B', rnd=msg_decoded.c_rnd, v_rnd=0,
                                                   v_val=None)
                        s_acceptor.sendto(msg_phase_1B.encode(), config['proposers'])
                elif current_instance in state_acceptor.keys() and msg_decoded.c_rnd > \
                        state_acceptor[current_instance]['rnd']:
                    state_acceptor[current_instance]['rnd'] = msg_decoded.c_rnd
                    if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                        msg_phase_1B = Message(current_instance, '1B', rnd=msg_decoded.c_rnd,
                                                   v_rnd=state_acceptor[current_instance]['v_rnd'],
                                                   v_val=state_acceptor[current_instance]['v_val'])
                        s_acceptor.sendto(msg_phase_1B.encode(), config['proposers'])
            elif current_phase == '2A' and current_instance in state_acceptor.keys():
                if msg_decoded.c_rnd >= state_acceptor[current_instance]['rnd']:
                    state_acceptor[current_instance]['v_rnd'] = msg_decoded.c_rnd
                    state_acceptor[current_instance]['v_val'] = msg_decoded.c_val
                    msg_phase_2B = Message(current_instance, '2B',
                                               v_rnd=state_acceptor[current_instance]['v_rnd'],
                                               v_val=state_acceptor[current_instance]['v_val'])
                    if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                        s_acceptor.sendto(msg_phase_2B.encode(), config['proposers'])
                    if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                        s_acceptor.sendto(msg_phase_2B.encode(), config['learners'])

            elif current_phase == 'CATCHUP':
                if current_instance in state_acceptor.keys():
                    if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                        msg_phase_1B = Message(current_instance, '1B', rnd=msg_decoded.c_rnd,
                                                   v_rnd=state_acceptor[current_instance]['v_rnd'],
                                                   v_val=state_acceptor[current_instance]['v_val'])
                        s_acceptor.sendto(msg_phase_1B.encode(), config['proposers'])


def monitoring():
    while True:
        for ky in list(state.keys()):
            if time.time() - state[ky]['time_stamp'] > Timeout and not state[ky][
                                                                                             'phase'] == 'DECISION':
                state[ky]['phase1B'] = 0
                state[ky]['phase2B'] = 0
                state[ky]['phase'] = '1A'
                state[ky]['k'] = 1
                state[ky]['k_v_val'] = None
                state[ky]['time_stamp'] = time.time()
                state[ky]['c_rnd'] += 2
                if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                    msg_phase_1A = Message(ky, '1A', c_rnd=state[ky]['c_rnd'])
                    s.sendto(msg_phase_1A.encode(), config['acceptors'])

def proposer(config, id):
    global state
    global s
    print('-> proposer', id)
    r = mcast_receiver(config['proposers'])
    s = mcast_sender()
    state = dict()
    threading.Thread(target=monitoring).start()
    quorum = math.ceil((Acceptors_num + 1) / 2)

    while True:
        msg = None
        msg = r.recv(2 ** 16)
        if msg is not None:
            client_message = True
            try:
                pickle.loads(msg)
                client_message = False
            except:
                None

            if client_message:
                state[len(state)] = {
                    'phase1B': 0,
                    'phase2B': 0,
                    'value': msg.decode(),
                    'phase': '1A',
                    'k': 1,
                    'k_v_val': None,
                    'time_stamp': time.time(),
                    'c_rnd': id
                }
                if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                    msg_phase_1A = Message(len(state) - 1, '1A',
                                               c_rnd=state[len(state) - 1]['c_rnd'])
                    s.sendto(msg_phase_1A.encode(), config['acceptors'])


            elif not client_message and len(state) > 0 and Message(0, 'DECODING').decode(msg).instance in list(
                    state.keys()):
                msg_decoded = Message(0, 'DECODING').decode(msg)
                current_instance = msg_decoded.instance
                current_phase = msg_decoded.phase
                message_rnd = msg_decoded.rnd
                message_v_rnd = msg_decoded.v_rnd
                message_v_val = msg_decoded.v_val
                if state[current_instance]['phase'] == '1A':
                    if message_rnd == state[current_instance]['c_rnd']:
                        state[current_instance]['phase1B'] += 1
                        if state[current_instance]['k'] < message_v_rnd:
                            state[current_instance]['k'] = message_v_rnd
                            state[current_instance]['k_v_val'] = message_v_val
                    if state[current_instance]['phase1B'] == quorum:
                        state[current_instance]['phase1B'] = -1
                        state[current_instance]['time_stamp'] = time.time()
                        value_to_be_proposed = state[current_instance]['value'] if \
                            state[current_instance]['k'] == 1 else \
                            state[current_instance]['k_v_val']
                        state[current_instance]['phase'] = '2A'
                        if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                            msg_phase_2A = Message(current_instance, '2A',
                                                       c_rnd=state[current_instance]['c_rnd'],
                                                       c_val=value_to_be_proposed)
                            s.sendto(msg_phase_2A.encode(), config['acceptors'])

                elif state[current_instance]['phase'] == '2A':
                    if current_phase == '2B' and message_v_rnd == state[current_instance]['c_rnd']:
                        state[current_instance]['phase2B'] += 1
                        if state[current_instance]['phase2B'] == quorum:
                            state[current_instance]['phase2B'] = -1
                            state[current_instance]['time_stamp'] = time.time()
                            value_to_be_proposed = message_v_val
                            state[current_instance]['phase'] = 'DECISION'

                elif current_phase == 'CATCHUP' and state[current_instance]['phase'] == 'DECISION':
                    for itr in range(current_instance, len(state.keys())):
                        if itr in state.keys():
                            if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                                phase_DECISION_message = Message(itr, 'DECISION',
                                                                 v_val=state[itr]['value'])
                                s.sendto(phase_DECISION_message.encode(),
                                         config['learners'])

                        else:
                            state[itr] = {
                                'phase1B': 0,
                                'phase2B': 0,
                                'phase': '1A',
                                'k': 0,
                                'k_v_val': None,
                                'time_stamp': time.time(),
                                'c_rnd': id
                            }
                            if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                                msg_phase_1A = Message(itr, 'CATCHUP', c_rnd=state[itr]['c_rnd'])
                                s.sendto(msg_phase_1A.encode(), config['acceptors'])
            elif len(state) > 0 and Message(0, 'DECODING').decode(msg).instance not in list(state.keys()):
                state[Message(0, 'DECODING').decode(msg).instance] = {
                    'phase1B': 0,
                    'phase2B': 0,
                    'value': None,
                    'phase': '1A',
                    'k': 0,
                    'k_v_val': None,
                    'time_stamp': time.time(),
                    'c_rnd': id
                }
                if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                    msg_phase_1A = Message(Message(0, 'DECODING').decode(msg).instance, 'CATCHUP',
                                               c_rnd=state[Message(0, 'DECODING').decode(msg).instance]['c_rnd'])
                    s.sendto(msg_phase_1A.encode(), config['acceptors'])

def monitoring_learner_catchup():
    prev_catchup = time.time()
    last_success = -1
    while True:
        if time.time() - prev_catchup > Timeout:
            if len(list(val_learn.keys())) > 0:
                if list(val_learn.keys())[0] == 0 and last_success == -1 and val_learn[0]['decision'] is True:
                    print(val_learn[0]['value'])
                    last_success = 0
                    sys.stdout.flush()

                elif list(val_learn.keys())[0] != 0 or last_success == -1:
                    msg_catchup = Message(0, 'CATCHUP')
                    if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                        s_learner.sendto(msg_catchup.encode(), config['proposers'])

                elif len(list(val_learn.keys())) > 1 and last_success + 1 < len(
                        list(val_learn.keys())) and last_success > -1:
                    for g in range(last_success + 1, len(list(val_learn.keys()))):
                        current_instance = list(val_learn.keys())[g]
                        previous_instance = list(val_learn.keys())[g - 1]
                        if current_instance - 1 == previous_instance and val_learn[current_instance]['decision'] \
                                is True:
                            print(val_learn[current_instance]['value'])
                            sys.stdout.flush()
                            last_success = current_instance

                        else:
                            msg_catchup = Message(list(val_learn.keys())[g - 1], 'CATCHUP')
                            if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                                s_learner.sendto(msg_catchup.encode(), config['proposers'])
                            break

                elif last_success + 1 == len(list(val_learn.keys())):
                    msg_catchup = Message(last_success, 'CATCHUP')
                    if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                        s_learner.sendto(msg_catchup.encode(), config['proposers'])
            else:
                msg_catchup = Message(0, 'CATCHUP')
                if np.random.uniform(low=0.0, high=1.0, size=None) > Loss:
                    s_learner.sendto(msg_catchup.encode(), config['proposers'])

            prev_catchup = time.time()

def learner(config, id):
    global s_learner
    global val_learn
    r = mcast_receiver(config['learners'])
    s_learner = mcast_sender()
    val_learn = dict()
    threading.Thread(target=monitoring_learner_catchup).start()
    quorum = math.ceil((Acceptors_num + 1) / 2)
    while True:
        msg = None
        msg = r.recv(2 ** 16)
        # print(msg)
        if msg is not None:
            msg_decoded = Message(0, 'DECODING').decode(msg)

            if msg_decoded.instance not in list(val_learn.keys()):
                val_learn[msg_decoded.instance] = {
                    'value': msg_decoded.v_val,
                    'quorum': 0,
                    'highest_vrnd': 0,
                    'decision': False
                }
            elif msg_decoded.phase == 'DECISION':
                val_learn[msg_decoded.instance] = {
                    'value': msg_decoded.v_val,
                    'quorum': np.inf,
                    'highest_vrnd': np.inf,
                    'decision': True
                }
            elif val_learn[msg_decoded.instance]['highest_vrnd'] < msg_decoded.v_rnd:
                val_learn[msg_decoded.instance] = {
                    'value': msg_decoded.v_val,
                    'quorum': 0,
                    'highest_vrnd': msg_decoded.v_rnd,
                    'decision': False
                }
            elif val_learn[msg_decoded.instance]['highest_vrnd'] == msg_decoded.v_rnd:
                val_learn[msg_decoded.instance]['quorum'] += 1
                if val_learn[msg_decoded.instance]['quorum'] == quorum:
                    val_learn[msg_decoded.instance]['decision'] = True

            val_learn = dict(sorted(val_learn.items()))
            sys.stdout.flush()



def client(config, id):
    print ('-> client ', id)
    s = mcast_sender()
    for value in sys.stdin:
        value = value.strip()
        print ("client: sending %s to proposers" % (value))
        s.sendto(value.encode(), config['proposers'])
    print ('client done.')
    #print(Acceptors_num)


if __name__ == '__main__':
        cfgpath = sys.argv[1]
        config = parse_cfg(cfgpath)
        role = sys.argv[2]
        id = int(sys.argv[3])
        if role == 'acceptor':
            rolefunc = acceptor
        elif role == 'proposer':
            rolefunc = proposer
        elif role == 'learner':
            rolefunc = learner
        elif role == 'client':
            rolefunc = client
        rolefunc(config, id)
