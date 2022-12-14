import numpy as np
import torch
import torch.nn as nn
from torchvision import datasets
import torchvision
import torchvision.transforms as transforms
from torch.utils.data.sampler import SubsetRandomSampler

from torch.nn import Sequential
from torch.nn import Conv2d
from torch.nn import BatchNorm2d
from torch.nn import Linear
from torch.nn import MaxPool2d
from torch.nn import ReLU
from torch.nn import LogSoftmax
from torch.nn import Dropout
from torch import flatten

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

def get_train_valid_loader(data_dir,batch_size, augment, random_seed, valid_size=0.1, shuffle=True):
    normalize = transforms.Normalize(mean=[0.4914, 0.4822, 0.4465], std=[0.2023, 0.1994, 0.2010])

    # define transforms
    valid_transform = transforms.Compose([transforms.Resize((227,227)), transforms.ToTensor(), normalize])
    
    if augment:
        train_transform = transforms.Compose([transforms.RandomCrop(32, padding=4),transforms.RandomHorizontalFlip(),transforms.ToTensor(),normalize])
    else:
        train_transform = transforms.Compose([transforms.Resize((227,227)),transforms.ToTensor(),normalize])

    # load the dataset
    train_dataset = datasets.CIFAR10(root=data_dir, train=True, download=True, transform=train_transform)

    valid_dataset = datasets.CIFAR10(root=data_dir, train=True,download=True, transform=valid_transform)

    num_train = len(train_dataset)
    indices = list(range(num_train))
    split = int(np.floor(valid_size * num_train))

    if shuffle:
        np.random.seed(random_seed)
        np.random.shuffle(indices)

    train_idx, valid_idx = indices[split:], indices[:split]
    train_sampler = SubsetRandomSampler(train_idx)
    valid_sampler = SubsetRandomSampler(valid_idx)

    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, sampler=train_sampler)
 
    valid_loader = torch.utils.data.DataLoader(valid_dataset, batch_size=batch_size, sampler=valid_sampler)

    return (train_loader, valid_loader)


def get_test_loader(data_dir, batch_size, shuffle=True):
    normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])

    # define transform
    transform = transforms.Compose([transforms.Resize((227,227)), transforms.ToTensor(), normalize])

    dataset = datasets.CIFAR10(root=data_dir, train=False, download=True, transform=transform)

    data_loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)

    return data_loader


# CIFAR10 dataset 
train_loader, valid_loader = get_train_valid_loader(data_dir = './data', batch_size = 64, augment = False, random_seed = 1)

test_loader = get_test_loader(data_dir = './data', batch_size = 64)

# Implementing AlexNet architecture
class AlexNet(nn.Module):
  def __init__(self,num_classes = 10):
    super(AlexNet,self).__init__()

    self.l1 = Sequential(
            Conv2d(3, 96, kernel_size=(11,11), stride=4, padding=0),
            ReLU(),
            MaxPool2d(kernel_size = (3,3), stride = 2))
    self.l2 = Sequential(
        Conv2d(96,256, kernel_size=(5,5), padding = 2),
        ReLU(),
        MaxPool2d(kernel_size=(3,3), stride = 2))
    self.l3 = Sequential(
        Conv2d(256,384, kernel_size=(3,3), padding=1),
        ReLU())
    self.l4 = Sequential(
        Conv2d(384,384, kernel_size=(3,3), padding=1),
        ReLU())
    self.l5 = Sequential(
        Conv2d(384,256, kernel_size=(3,3), padding=1),
        ReLU(),
        MaxPool2d(kernel_size = 3, stride = 2))
    self.fc = Sequential(
        Dropout(0.5),
        Linear(9216, 4096),
        ReLU())
    self.fc1 = Sequential(
        Dropout(0.5),
        Linear(4096, 4096),
        ReLU())
    self.fc2= Sequential(
        Linear(4096, num_classes))
    
  def forward(self, x):
        out = self.l1(x)
        out = self.l2(out)
        out = self.l3(out)
        out = self.l4(out)
        out = self.l5(out)
        out = out.reshape(out.size(0), -1)
        out = self.fc(out)
        out = self.fc1(out)
        out = self.fc2(out)
        return out

# Hyper-parameters
num_classes = 10
num_epochs = 2
batch_size = 64
learning_rate = 0.005

model = AlexNet(num_classes).to(device)

# Creating the loss function and optimizer object
criterion = nn.CrossEntropyLoss()
# SGD optimizer works much better than Adam optimizer in this architecture.
optimizer = torch.optim.SGD(model.parameters(), lr=learning_rate, weight_decay = 0.005, momentum = 0.9)  

# Train the model
total_step = len(train_loader)

# Training the model
total_step = len(train_loader)

for epoch in range(num_epochs):
    for i, (images, labels) in enumerate(train_loader):  
        images = images.to(device)
        labels = labels.to(device)
        
        outputs = model(images)
        loss = criterion(outputs, labels)
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    print ('Epoch [{}/{}], Step [{}/{}], Loss: {:.4f}'.format(epoch+1, num_epochs, i+1, total_step, loss.item()))
            
    # Testing the model and evaluating the accuracy
    with torch.no_grad():
        correct = 0
        total = 0
        for images, labels in valid_loader:
            images = images.to(device)
            labels = labels.to(device)
            outputs = model(images)
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            del images, labels, outputs
    
        print('Accuracy of the model on the test images: {} %'.format(100 * correct / total))
