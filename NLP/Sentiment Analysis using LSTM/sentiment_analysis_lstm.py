import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

import numpy as np
import pandas as pd

from utils import process_tweet

from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

import matplotlib.pyplot as plt

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
# device

train_path = "train.csv"
test_path = "test.csv"

train_df = pd.read_csv(train_path)
test_df = pd.read_csv(test_path)

# Cleaning the data

# Removing Tweet's containing text "Not Available"
train_df = train_df.drop(columns=["Id"])
train_df = train_df.dropna()

# Removing Tweet's containing text "Not Available"
train_df = train_df[train_df['Tweet']!="Not Available"]

# train_df

test_df = test_df.rename(columns={"Category": "Tweet"})
test_df = test_df.dropna()
test_df = test_df[test_df['Tweet']!="Not Available"]
test_df = test_df.drop(columns=["Id"])
# test_df

# Checking for bias in dataset
# train_df["Category"].value_counts()

# Undersampling to get rid of the bias
rem_pos = 2599 - 869
rem_neut = 1953 - 869

neg_df = train_df[train_df["Category"] == "negative"] 

pos_df = train_df[train_df["Category"] == "positive"]
neut_df = train_df[train_df["Category"] == "neutral"]

# pos_df

# Generating a random list of indices whose elements are to be deleted in the positive and neutral tweets
# replace = False, ensures no two chosen indices are same
pos_drop_indices = np.random.choice(pos_df.index, rem_pos, replace=False)
neut_drop_indices = np.random.choice(neut_df.index, rem_neut, replace=False)

pos_undersampled = pos_df.drop(pos_drop_indices)
neut_undersampled = neut_df.drop(neut_drop_indices)

# Creating the updated train dataset by concatenating records of all three types - positive, negative and neutral
balanced_train_df = pd.concat([neg_df,pos_undersampled,neut_undersampled])
balanced_train_df["Category"].value_counts()
# balanced_train_df

# Splitting train dataset into validation and train dataset
train_clean_df, test_clean_df = train_test_split(balanced_train_df, test_size=0.15)

train_set = list(train_clean_df.to_records(index=False))
test_set = list(test_clean_df.to_records(index=False))

# train_set[:10]

# Using the process_tweet function in utils.py to process the tweets removing unnecessary text.

train_set = [(label, process_tweet(tweet)) for label, tweet in train_set]
# train_set

test_set = [(label, (process_tweet(tweet))) for label, tweet in test_set]

# Creating the vocabulary from the training dataset (train + validation)
index2word = ["<PAD>", "<SOS>", "<EOS>"]

for ds in [train_set, test_set]:
    for label, tweet in ds:
        for word in tweet:
            if word not in index2word:
                index2word.append(word)
# index2word

word2index = {word: idx for idx, word in enumerate(index2word)}
# len(word2index)

# Function to encode the outputs
def label_map(label):
    if label == "negative":
        return 0
    elif label == "neutral":
        return 1
    else: #positive
        return 2

# Defining the maximum sequence length
# If a tweet is longer than this, it is truncated
# If a tweet is shorter than this, it is padded with zeroes
seq_length = 32

def encode_and_pad(tweet, length):
    sos = [word2index["<SOS>"]]
    eos = [word2index["<EOS>"]]
    pad = [word2index["<PAD>"]]

    if len(tweet) < length - 2: # -2 for SOS and EOS
        n_pads = length - 2 - len(tweet)
        encoded = [word2index[w] for w in tweet]
        return sos + encoded + eos + pad * n_pads 
    else: # tweet is longer than possible; truncating
        encoded = [word2index[w] for w in tweet]
        truncated = encoded[:length - 2]
        return sos + truncated + eos

# Converting the words in the tweets and the output labels to numbers to input into our neural network.
train_encoded = [(encode_and_pad(tweet, seq_length), label_map(label)) for label, tweet in train_set]

test_encoded = [(encode_and_pad(tweet, seq_length), label_map(label)) for label, tweet in test_set]

"""Creating the DataLoaders"""

# Size of the batch
batch_size = 32

# Tweets in training dataset
train_x = np.array([tweet for tweet, label in train_encoded])
# Output labels in training dataset
train_y = np.array([label for tweet, label in train_encoded])
# Tweets in validation dataset
test_x = np.array([tweet for tweet, label in test_encoded])
# Output labels in validation dataset
test_y = np.array([label for tweet, label in test_encoded])

train_ds = TensorDataset(torch.from_numpy(train_x), torch.from_numpy(train_y))
test_ds = TensorDataset(torch.from_numpy(test_x), torch.from_numpy(test_y))

# drop_last=True is used when the final batch does not have 32 elements. It will cause dimension errors if we feed it into the model. 
# By setting this parameter to True, we avoid this final batch.

train_dl = DataLoader(train_ds, shuffle=True, batch_size=batch_size, drop_last=True)
test_dl = DataLoader(test_ds, shuffle=True, batch_size=batch_size, drop_last=True)

"""Building the LSTM Model"""

class LSTM(torch.nn.Module) :
    def __init__(self, vocab_size, embedding_dim, hidden_dim, dropout) :
        super().__init__()

        # Instead of using one-hot encoded vector for each word, with just one '1',
        # we can have multiple non-zero continous entries, which would reduce size of vector
        # An embedding layer creates a look-up table mapping each word, to a lower dimension vector.
        # The embedding parameters are trainable
        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)

        # hidden_dim : Size of hidden state and cell state of the LSTM
        self.lstm = nn.LSTM(embedding_dim, hidden_dim, batch_first=True)
        self.dropout = nn.Dropout(dropout)
        # Take the hidden dim of LSTM and maps it to score of each of the 3 outputs.
        self.fc = nn.Linear(hidden_dim, 3)

    def forward(self, x, hidden):

      # Forward takes in input and previous hidden state

        # The input is transformed to its embedding vector
        embs = self.embedding(x)

        # The embedded inputs are fed to the LSTM alongside the previous hidden state
        # We get the output and next hidden state.
        out, hidden = self.lstm(embs, hidden)

        out = self.dropout(out)
        out = self.fc(out)

        # Extracting the scores for the final hidden state since it is the one that matters.
        out = out[:, -1]
        return out, hidden
    
    # Initializing the initial hidden states
    def init_hidden(self):
        return (torch.zeros(1, batch_size, 32), torch.zeros(1, batch_size, 32))

"""Training the model"""

# Embedding dimension : 64
# Hidden dimension : 32
# dropout : 0.2
model = LSTM(len(word2index), 64, 32, 0.2)
model = model.to(device)

criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr = 3e-4)

epochs = 100
losses = []
for e in range(epochs):

    h0, c0 =  model.init_hidden()

    h0 = h0.to(device)
    c0 = c0.to(device)

    for batch_idx, batch in enumerate(train_dl):

        input = batch[0].to(device)
        target = batch[1].to(device)

        optimizer.zero_grad()
        with torch.set_grad_enabled(True):
            out, hidden = model(input, (h0, c0))
            loss = criterion(out, target)
            loss.backward()
            optimizer.step()
    losses.append(loss.item())

plt.plot(losses)

batch_acc = []
for batch_idx, batch in enumerate(test_dl):

    input = batch[0].to(device)
    target = batch[1].to(device)

    optimizer.zero_grad()
    with torch.set_grad_enabled(False):
        out, hidden = model(input, (h0, c0))
        _, preds = torch.max(out, 1)
        preds = preds.to("cpu").tolist()
        batch_acc.append(accuracy_score(preds, target.tolist()))

sum(batch_acc)/len(batch_acc)
