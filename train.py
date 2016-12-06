from __future__ import print_function
import numpy as np
import tensorflow as tf

import argparse
import time
import os
from six.moves import cPickle

from utils import DataLoader
from model import Model

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file', type=str, nargs=1,
                       help='input data file')
    parser.add_argument('--save_dir', type=str, default='save',
                       help='directory to store checkpointed models')
    parser.add_argument('--rnn_size', type=int, default=128,
                       help='size of RNN hidden state')
    parser.add_argument('--batch_size', type=int, default=50,
                       help='minibatch size')
    parser.add_argument('--seq_length', type=int, default=10,
                       help='RNN sequence length')
    parser.add_argument('--num_epochs', type=int, default=50,
                       help='number of epochs')
    parser.add_argument('--learning_rate', type=float, default=0.002,
                       help='learning rate')
    parser.add_argument('--init_from', type=str, default=None,
                       help="""continue training from saved model at this path. Path must contain files saved by previous training process: 
                            'config.pkl'        : configuration;
                            'chars_vocab.pkl'   : vocabulary definitions;
                            'checkpoint'        : paths to model file(s) (created by tf).
                                                  Note: this file contains absolute paths, be careful when moving files around;
                            'model.ckpt-*'      : file(s) with model definition (created by tf)
                        """)
    args = parser.parse_args()
    train(args)


def train(args):
    data_loader = DataLoader(args.input_file[0], args.batch_size, args.seq_length)
    args.vocab_size = data_loader.vocab_size
    
    # check compatibility if training is continued from previously saved model
    if args.init_from is not None:
        check_compat(args, data_loader)
        
    with open(os.path.join(args.save_dir, 'config.pkl'), 'wb') as f:
        cPickle.dump(args, f)
    with open(os.path.join(args.save_dir, 'chars_vocab.pkl'), 'wb') as f:
        cPickle.dump((data_loader.chars, data_loader.vocab), f)
        
    model = Model(args)

    with tf.Session() as sess:
        tf.initialize_all_variables().run()
        saver = tf.train.Saver(tf.all_variables())
        # restore model
        if args.init_from is not None:
            saver.restore(sess, ckpt.model_checkpoint_path)
        for i in range(args.num_epochs):
            data_loader.reset_batch_pointer()
            state = model.initial_state.eval()
            for b in range(data_loader.num_batches):
                start = time.time()
                x, e, y = data_loader.next_batch()
                feed = {model.targets: y, model.initial_state: state}
                for j in range(args.seq_length):
                    feed[model.node_data[j].name] = x[j]
                    feed[model.edge_data[j].name] = e[j]
                train_loss, state, _ = sess.run([model.cost, model.final_state, model.train_op], feed)
                end = time.time()
                print("{}/{} (epoch {}), train_loss = {:.3f}, time/batch = {:.3f}" \
                    .format(i * data_loader.num_batches + b,
                            args.num_epochs * data_loader.num_batches,
                            i, train_loss, end - start))
            checkpoint_path = os.path.join(args.save_dir, 'model.ckpt')
            saver.save(sess, checkpoint_path)
            print("model saved to {}".format(checkpoint_path))


def check_compat(args, data_loader):
    # check if all necessary files exist 
    assert os.path.isdir(args.init_from)," %s must be a a path" % args.init_from
    assert os.path.isfile(os.path.join(args.init_from,"config.pkl")),"config.pkl file does not exist in path %s"%args.init_from
    assert os.path.isfile(os.path.join(args.init_from,"chars_vocab.pkl")),"chars_vocab.pkl.pkl file does not exist in path %s" % args.init_from
    ckpt = tf.train.get_checkpoint_state(args.init_from)
    assert ckpt,"No checkpoint found"
    assert ckpt.model_checkpoint_path,"No model path found in checkpoint"

    # open old config and check if models are compatible
    with open(os.path.join(args.init_from, 'config.pkl')) as f:
        saved_model_args = cPickle.load(f)
    need_be_same=["model","rnn_size","num_layers","seq_length"]
    for checkme in need_be_same:
        assert vars(saved_model_args)[checkme]==vars(args)[checkme],"Command line argument and saved model disagree on '%s' "%checkme
    
    # open saved vocab/dict and check if vocabs/dicts are compatible
    with open(os.path.join(args.init_from, 'chars_vocab.pkl')) as f:
        saved_chars, saved_vocab = cPickle.load(f)
    assert saved_chars==data_loader.chars, "Data and loaded model disagree on character set!"
    assert saved_vocab==data_loader.vocab, "Data and loaded model disagree on dictionary mappings!"

if __name__ == '__main__':
    main()
