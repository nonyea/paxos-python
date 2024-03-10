import pickle


class Message:

    def __init__(self, instance, phase, c_rnd=None, c_val=None, rnd=None, v_rnd=None, v_val=None):

        self.instance = instance
        self.phase = phase
        self.c_rnd = None
        self.c_val = None
        self.rnd = None
        self.v_rnd = None
        self.v_val = None

        if self.phase == '1A':
            self.c_rnd = c_rnd

        elif self.phase == '1B':
            self.rnd = rnd
            self.v_rnd = v_rnd
            self.v_val = v_val

        elif self.phase == '2A':
            self.c_rnd = c_rnd
            self.c_val = c_val

        elif self.phase == '2B':
            self.v_rnd = v_rnd
            self.v_val = v_val

        elif self.phase == 'DECISION':
            self.v_val = v_val

        elif self.phase == 'CATCHUP':
            None #the learners just set the last continuous instance received, the proposer respond with a decision

    def encode(self):
        return pickle.dumps(vars(self))

    def decode(self, encoded):
        data = pickle.loads(encoded)
        self.instance = data['instance']
        self.phase = data['phase']
        self.c_rnd = data['c_rnd']
        self.c_val = data['c_val']
        self.rnd = data['rnd']
        self.v_rnd = data['v_rnd']
        self.v_val = data['v_val']
        self.phase = data['phase']
        return self

    def __str__(self):
        return f'instance: {self.instance}, phase: {self.phase}, c_rnd: {self.c_rnd}, c_val: {self.c_val},' \
               f' rnd: {self.rnd}, v_rnd: {self.v_rnd}, v_val: {self.v_val}'
