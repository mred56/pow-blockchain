from functools import reduce

import json
from urllib import response
import requests

from block import Block #importing block class
from transaction import Transaction
from utility.verification import Verification
from utility.hash_util import hash_block
from wallet import Wallet

# The reward we give to miners (for creating a new block)
MINING_REWARD = 10

print(__name__)


class Blockchain:
    def __init__(self, public_key, node_id):
        # Our starting block for the blockchain
        # Will be overwritten if we load_data()
        genesis_block = Block(0, '', [], 100, 0)
        # Initializing our (empty) blockchain list
        self.chain = [genesis_block] #__ private ish
        # Unhandled transactions
        self.__open_transactions = []
        self.public_key = public_key
        self.__blockchain_nodes = set() #set accepts only unique values, no node can be added twice
        self.node_id = node_id
        self.resolve_conflicts = False
        self.load_data()

    @property #used as a getter
    def chain(self):
        return self.__chain[:] #copy of chain
    
    @chain.setter
    def chain(self, val):
        self.__chain = val

    def get_open_transactions(self):
        return self.__open_transactions[:]


    def load_data(self):
        """Initialize blockchain + open transactions data from a file."""
        try:
            with open('blockchain-{}.txt'.format(self.node_id), mode='r') as f:
                # file_content = pickle.loads(f.read())
                file_content = f.readlines()
                # blockchain = file_content['chain']
                # open_transactions = file_content['ot']
                blockchain = json.loads(file_content[0][:-1])
                updated_blockchain = []
                # We need to convert  the loaded data because Transactions should use OrderedDict
                for block in blockchain:
                    converted_tx = [Transaction(tx['sender'], tx['recipient'], tx['signature'], tx['amount'], tx['action']) for tx in block['transactions']]
                    #loading previous blocks
                    updated_block = Block(block['index'], block['previous_hash'], converted_tx, block['proof'], block['timestamp'])
                    updated_blockchain.append(updated_block)
                self.chain = updated_blockchain
                open_transactions = json.loads(file_content[1][:-1])
                # We need to convert  the loaded data because Transactions should use OrderedDict
                updated_transactions = []
                for tx in open_transactions:
                    updated_transaction = Transaction(tx['sender'], tx['recipient'], tx['signature'], tx['amount'], tx['action'])
                    updated_transactions.append(updated_transaction)
                self.__open_transactions = updated_transactions
                blockchain_nodes = json.loads(file_content[2])
                self.__blockchain_nodes = set(blockchain_nodes)
        except (IOError, IndexError):
            print('Handled exception')
        finally: #runs no matter if error occurs or not
            print('cleanup')


    def save_data(self):
        """Save blockchain + open transactions snapshot to a file."""
        try:
            #wb writes binary data, .p is for pickle
            with open('blockchain-{}.txt'.format(self.node_id), mode='w') as f:
                saveable_chain = [block.__dict__ for block in [Block(block_el.index, block_el.previous_hash, [tx.__dict__ for tx in block_el.transactions],block_el.proof, block_el.timestamp) for block_el in self.__chain]] #creating dicts for json
                f.write(json.dumps(saveable_chain))
                f.write('\n')
                saveable_tx = [tx.__dict__ for tx in self.__open_transactions] #creating dicts for json
                f.write(json.dumps(saveable_tx))
                f.write('\n')
                f.write(json.dumps(list(self.__blockchain_nodes)))

                # save_data = {
                #     'chain': blockchain,
                #     'ot': open_transactions
                # }
                # f.write(pickle.dumps(save_data))
        except IOError:
            print('Saving failed!')


    def proof_of_work(self):
        """Generate a proof of work for the open transactions, the hash of the previous block and a random number (which is guessed until it fits)."""
        last_block = self.__chain[-1]
        last_hash = hash_block(last_block)
        nonce = 0
        # Try different PoW numbers and return the first valid one
        while not Verification.valid_proof(self.__open_transactions, last_hash, nonce):
            nonce += 1
        return nonce


    def get_balance(self, sender = None):
        if sender == None:
            if self.public_key == None:
                return None
            #make a list of transaction amounts from the transactions list in a block if the sender is our participant
            participant = self.public_key
        else:
            participant = sender
        tx_sender = [[tx.amount for tx in block.transactions if tx.sender == participant] for block in self.__chain]
        #make a list of transaction amounts from the transaction in open_transactions if the sender is our participant
        open_tx_sender = [tx.amount for tx in self.__open_transactions if tx.sender == participant]
        #append the second list to the first
        tx_sender.append(open_tx_sender)
        #uses the tx_sender list, with initial value 0. Goes through the tx_sender list as a tx_amount iterable and adds up all the elements
        amount_sent = reduce(lambda tx_sum, tx_amount: tx_sum + sum(tx_amount) if len(tx_amount)>0 else tx_sum + 0, tx_sender, 0)
        
        tx_recipient = [[tx.amount for tx in block.transactions if tx.recipient == participant] for block in self.__chain]
        amount_received = reduce(lambda tx_sum, tx_amount: tx_sum + sum(tx_amount) if len(tx_recipient)>0 else tx_sum + 0, tx_recipient, 0)
        
        return amount_received - amount_sent


    def get_last_blockchain_value(self):
        """Returns the last value of the current blockchain"""
        if len(self.__chain) < 1:
            return None #used to tell your program there is nothing
        return self.__chain[-1]


    def add_transaction(self, recipient, sender, signature, action, amount=1.0, is_receiving=False):
        """ Append a new value as well as the last blockchain value to the blockchain.

        Arguments: 
            :sender: sender of coins
            :recipient: recieves coins
            :amount: coins sent with a transaction (default is 1 coin)
        """
        #dictionary {'key': value}
        # transaction = { 
        #     'sender': sender, 
        #     'recipient': recipient, 
        #     'amount': amount
        # }
        # if self.public_key == None:
        #     return False
        transaction = Transaction(sender, recipient, signature, amount, action)
        if Verification.verify_transaction(transaction, self.get_balance):
            self.__open_transactions.append(transaction)
            self.save_data()
            if not is_receiving:
                for node in self.__blockchain_nodes:
                    url = 'http://{}/broadcast-transaction'.format(node)
                    try:
                        response = requests.post(url, json={'sender': sender, 'recipient': recipient, 'amount': amount, 'signature': signature, 'action': action})
                        if response.status_code == 400 or response.status_code == 500:
                            print('Transaction decline, needs resolving')
                            return False
                    except requests.exceptions.ConnectionError:
                        continue
            return True
        return False


    def mine_block(self): #node as argument??
        '''Create a new block and add open transactions to it'''
        #pass - don't do anything with this function
        #Fetch the currently last block of the blockchain
        if self.public_key == None:
            return None
        last_block = self.__chain[-1]
        #Hash the last block to be able to compare it to the stored hash value
        hashed_block = hash_block(last_block)
        proof = self.proof_of_work()
        
        #Reward for the miners
        # reward_transaction = {
        #     'sender': 'MINING',
        #     'recipient': owner,
        #     'amount': MINING_REWARD
        # }
        reward_transaction = Transaction('MINING', self.public_key, '', MINING_REWARD, 'Mining')
        #Copy transaction instead of manipulating the original open_transactions
        #This is in case mining fails, we have the copies
        copied_transactions = self.__open_transactions[:] #copying the open_transaction list by value
        for tx in copied_transactions:
            if not Wallet.verify_transaction(tx):
                return None
        copied_transactions.append(reward_transaction)
        #creating a new block
        block = Block(len(self.__chain),hashed_block, copied_transactions, proof)
        
        self.__chain.append(block)
        #reset open transactions
        self.__open_transactions = []
        self.save_data()
        for node in self.__blockchain_nodes:
            url = 'http://{}/broadcast-block'.format(node)
            converted_block = block.__dict__.copy()
            converted_block['transactions'] = [tx.__dict__ for tx in converted_block['transactions']]
            try:
                response = requests.post(url, json={'block': converted_block})
                if response.status_code == 400 or response.status_code == 500:
                    print('Block declined, needs resolving')
                if response.status_code == 409:
                    self.resolve_conflicts = True
            except requests.exceptions.ConnectionError:
                continue
        return block

    
    def add_block(self, block):
        transactions = [Transaction(
            tx['sender'], tx['recipient'], tx['signature'], tx['amount'], tx['action']) for tx in block['transactions']]
        proof_is_valid = Verification.valid_proof(
            transactions[:-1], block['previous_hash'], block['proof'])
        hashes_match = hash_block(self.chain[-1]) == block['previous_hash']
        if not proof_is_valid or not hashes_match:
            return False
        converted_block = Block(
            block['index'], block['previous_hash'], transactions, block['proof'], block['timestamp'])
        self.__chain.append(converted_block)
        stored_transactions = self.__open_transactions[:]
        for itx in block['transactions']: #incoming transactions
            for opentx in stored_transactions:
                if opentx.sender == itx['sender'] and opentx.recipient == itx['recipient'] and opentx.amount == itx['amount'] and opentx.signature == itx['signature'] and opentx.action == itx['action']:
                    try:
                        self.__open_transactions.remove(opentx)
                    except ValueError:
                        print('Item was already removed')
        self.save_data()
        return True


    def add_blockchain_node(self, node):
        """Adds a new node to a blockchain_nodes set
        
        Arguments:
            :node: The node URL which should be added
        """

        self.__blockchain_nodes.add(node)
        self.save_data() #save the nodes to a txt file

    
    def remove_blockchain_node(self, node):
        """Rremoves a node from a blockchain_nodes set
        
        Arguments:
            :node: The node URL which should be removed
        """
        self.__blockchain_nodes.discard(node) #doesn't throw an error if there is no node in the set
        self.save_data()

    
    def get_blockchain_nodes(self):
        """Return a list of all blockchain nodes"""
        return list(self.__blockchain_nodes) #returns a copy


    def resolve(self):
        winner_chain = self.chain
        replace = False
        for node in self.__blockchain_nodes:
            url = 'http://{}/chain'.format(node) #get_chain method in node.py
            try:
                response = requests.get(url)
                node_chain = response.json()
                node_chain = [Block(block['index'], block['previous_hash'], [Transaction(
                    tx['sender'], tx['recipient'], tx['signature'], tx['amount'], tx['action']) for tx in block['transactions']],
                                    block['proof'], block['timestamp']) for block in node_chain]
                node_chain_length = len(node_chain)
                local_chain_length = len(winner_chain)
                if node_chain_length > local_chain_length and Verification.verify_chain(node_chain):
                    winner_chain = node_chain
                    replace = True
            except requests.exceptions.ConnectionError:
                continue
        self.resolve_conflicts = False
        self.chain = winner_chain
        if replace:
            self.__open_transactions = []
        self.save_data()
        return replace




