import torch
from fashion_dataset import *
from module import *
from torch.utils.data.dataloader import DataLoader
from tqdm import tqdm
from torch import optim


epochs=8
#net
net=Net().to(device)



def get_optimizer(net):
    return optim.Adam(net.parameters())
loss_fn = nn.CrossEntropyLoss()
def _train_supervised( train_loader_,net,loss_fn=loss_fn,epochs=epochs):
    # set model to train mode
    net.train()
    for i in range(epochs):
        corrects = 0
        optimizer=get_optimizer(net)
        #for inputs, labels in tqdm(train_loader, leave=False):
        for inputs, labels in train_loader_:
            optimizer.zero_grad()
            outputs:torch.Tensor = net(inputs)
            loss:torch.Tensor = loss_fn(outputs,labels)
            loss.backward()
            optimizer.step()
            preds = outputs.argmax(1).detach()
            corrects += (preds==labels.data).sum()
            acc=(corrects / len(train_loader_.dataset)).item()
        print("epoch",i,"loss",loss.item(),"acc",acc)
    return loss, acc

def generate_final_output():
    import os
    os.makedirs("out",exist_ok=True)
    net.eval()
    with torch.no_grad():
        x=torch.stack([final_dataset[i] for i in range(len(final_dataset))])
        #加入softmax的目的是为了排除极端预测影响整个结果
        y=F.softmax(net(x),dim=-1)
        for i in transform_offset(x):
            y+=F.softmax(net(i),dim=-1)
        y=y.argmax(1).detach().cpu().unsqueeze(0)
        y=y.numpy()
    print("shape",y.shape)
    test_acc=_test(test_loader,net)
    np.save(f"out/output_{test_acc}.npy",y)

def semi_supervised_training_with_regularization(unlabeled_dataloader, labeled_dataloader, model, criterion=loss_fn, optimizer_getter=get_optimizer, num_epochs=epochs, lambda_l2=0.01):
    """
    进行带L2正则化的半监督学习的训练过程。

    参数:
    - unlabeled_dataloader: 无标签数据集的DataLoader
    - labeled_dataloader: 有标签数据集的DataLoader
    - model: 要训练的模型
    - criterion: 损失函数
    - optimizer: 优化器
    - num_epochs: 训练的轮数
    - lambda_l2: L2正则化的系数
    """
    model.train()  # 设置模型为训练模式
    optimizer=optimizer_getter(model)
    for epoch in range(num_epochs):
        # 为无标签的数据生成伪标签并进行训练
        for data,(x,y) in zip(unlabeled_dataloader,labeled_dataloader):
            optimizer.zero_grad()
            outputs:torch.Tensor = model(x)
            loss = criterion(outputs, y)
            loss.backward()
            optimizer.step()

            optimizer.zero_grad()
            with torch.no_grad():  # 不计算生成伪标签的梯度
                pseudo_labels = model(data).argmax(dim=1)  # 生成伪标签
            outputs = model(data)
            loss = criterion(outputs, pseudo_labels)  # 使用伪标签计算损失
            
            # 添加L2正则化
            l2_reg = torch.tensor(0.).to(data.device)
            for param in model.parameters():
                l2_reg += torch.norm(param)
            loss += lambda_l2 * l2_reg
            
            loss.backward()
            optimizer.step()

        print(f'Epoch [{epoch+1}/{num_epochs}] completed')


def _test(test_loader, net,isOffset=True):
    # set model to eval mode
    net.eval()
    corrects = 0
    with torch.no_grad():
        for inputs, labels in tqdm(test_loader, leave=False):
            outputs = F.softmax(net(inputs),dim=-1)
            if isOffset:
                for i in transform_offset(inputs):
                    outputs+=F.softmax(net(i),dim=-1)
            preds = outputs.argmax(1).detach()
            corrects += (preds==labels.data).sum()
    return (corrects / len(test_loader.dataset)).item()


def train_supervised(epochs=epochs):
    print("start supervised")
    train_data=_train_supervised(train_loader,net,epochs=epochs)
    print("train accuarcy: ",train_data[1])
def train_supervised_enhanced(offset=2,epochs=epochs):
    enhanced_dataset=EnhancedDataset(train_dataset,offset=offset)
    train_loader_=DataLoader(enhanced_dataset,batch_size=batch_size,shuffle=True)
    print("start supervised_enhanced with offset: ",offset)
    train_data=_train_supervised(train_loader_,net,epochs=epochs)
    print("train accuarcy: ",train_data[1])
def train_supervised_rotated(epochs=epochs):
    print("start supervised_rotated")
    enhanced_dataset=RotatedDataset(train_dataset)
    train_loader_=DataLoader(enhanced_dataset,batch_size=batch_size,shuffle=True)
    train_data=_train_supervised(train_loader_,net,epochs=epochs)
    print("train accuarcy: ",train_data[1])
def train_semi_supervised(lambda_l2=0.001,epochs=epochs):
    print("start semi supervised")
    enhanced_dataset=EnhancedDataset(train_dataset,offset=2)
    train_loader_=DataLoader(enhanced_dataset,batch_size=batch_size,shuffle=True)
    train_data=semi_supervised_training_with_regularization(unlabeled_loader,train_loader_,net,lambda_l2=lambda_l2,num_epochs=epochs)
    #print("train accuarcy: ",train_data[1])
def test(isOffset=True):
    #print("start test")
    test_data=_test(test_loader,net,isOffset)
    print("test: ",test_data)

# --- TRAIN ---
if __name__=="__main__":
    trains=[
        lambda:train_supervised(epochs=1),
        #lambda:train_supervised_rotated(epochs=1),
        lambda:train_semi_supervised(epochs=1),
        lambda:train_supervised_enhanced(2,epochs=1),
        lambda:train_supervised_enhanced(1,epochs=1),
    ]
    for _ in range(epochs):
        for train in trains:
            train()
            test()
    generate_final_output()