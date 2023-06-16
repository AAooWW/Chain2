import os
from flask import request, render_template, session, redirect
from typing import List, Tuple
import traceback
import time
import matplotlib.pyplot as plt
import threading
from matplotlib import rcParams
import pandas as pd



from werkzeug.utils import secure_filename

from __init__ import app
from client.signer_impl import Signer_Impl
from eth_utils.address import to_checksum_address
from models import Contracts, Container, Maritime, IPFSObject, db, count_numbers
from blockchain import signin_account, create_account, deploy_contract, call_contract
from crypto import gen_rsakey, shamir_encode, aes_encode
from ipfs import ipfs_client


def load():
    pass


def login(username, password) -> Tuple[Container, Signer_Impl]:
    if username == "":
        return None, None  # input error
    container = Container.query.filter(Container.username == username).first()
    if container is None:
        # no such user
        return signup(username, password)

    if container.password != password:
        return None, None  # password error
    signer = signin_account(username, password)
    if signer is None:
        return None, None  # password error
    return container, signer


def signup(username, password) -> Tuple[Container, Signer_Impl]:
    try:
        signer = create_account(username, password)

        container = Container(username=username, password=password)

        contract_addr = deploy_contract("Enterprise", signer=signer)      #合约要改
        container.contract_addr = contract_addr
        container.account_addr = str(signer.keypair.address)
        container.account_pub = str(signer.keypair.public_key)
        container.account_priv = str(signer.keypair.private_key)

        privkey, pubkey = gen_rsakey()
        container.envelope_pub = pubkey
        container.envelope_priv = privkey

        managementAddr = db.session.query(Contracts).filter(Contracts.name == "Management").first().addr

        call_contract(managementAddr, "Management", "addEnterprise",                   #合约要改，addContainer
                      args=[
                          username,
                          to_checksum_address(container.account_addr),
                          to_checksum_address(container.contract_addr),
                          container.envelope_pub, ""])

        db.session.add(container)
        db.session.commit()
    except Exception:
        traceback.print_exc()
        db.session.rollback()
        return None, None
    return container, signer


@app.route("/container", methods=["GET", "POST"])
def container():
    if request.method == "GET":
        username = session.get("username", "")
        password = session.get("password", "")
        container, signer = login(username, password)
        if container is None or signer is None:
            return render_template("container2.html", is_login=False)            #页面需修改

        goods_Addr = db.session.query(Contracts).filter(Contracts.name == "Im_goods").first().addr

        try:
            Goodsdata = call_contract(goods_Addr, "Im_goods", "getGoodsReports", args=[str(container.account_addr)],
                                      signer=signer)

            goodsdata = list(zip(*Goodsdata))

        except Exception:
            return render_template("container2.html", is_login=True, container=container, username=username)

        return render_template("container2.html", is_login=True, container=container,
            username=username, goodsdata=goodsdata)



    username = request.form.get("name", "")
    password = request.form.get("password", "")
    container, signer = login(username, password)

    if container is None or signer is None:
        return render_template("container2.html", is_login=False, fail_msg="登录失败")

    session["username"] = username
    session["password"] = password

    goods_Addr = db.session.query(Contracts).filter(Contracts.name == "Im_goods").first().addr

    try :
        Goodsdata = call_contract(goods_Addr, "Im_goods", "getGoodsReports", args=[str(container.account_addr)],
                                signer=signer)

        goodsdata = list(zip(*Goodsdata))

    except Exception:
        return render_template("container2.html", is_login=True, succ_msg="登录成功", container=container,  username=username)

    return render_template("container2.html", is_login=True, succ_msg="登录成功", container=container, username=username, goodsdata = goodsdata )




@app.route("/container/report_goods_info",methods=["GET", "POST"])

def enterprise_report_goods_info():

    username = session.get("username", "")
    password = session.get("password", "")
    container, signer = login(username, password)

    if container is None:
        return redirect("/container")

    if request.method == "GET":
        return render_template("container2-1.html", is_login = True, container=container, username = username)

    # return render_template("container2-1.html", is_login=True, container=container, username=username)

    goods_id = int(request.form.get("goods-id"))
    goods_type = request.form.get("goods-type")
    goods_name = request.form.get("goods-name")
    goods_he = int(request.form.get("goods-he"))

    # try:
    goods_Addr = db.session.query(Contracts).filter(Contracts.name == "Im_goods").first().addr

    # 定义 x 坐标轴(进行 call_contract 的次数) 和 y 坐标轴(每次 call_contract 的延迟) 的列表
    x_axis = []
    y_axis = []

    for concurrency in range(10, 51, 10):
        threads = []
        start_time = time.time()
        for i in range(concurrency):
            Goods_id = int(i) + goods_id
            args = [Goods_id, goods_type, goods_name, goods_he, str(container.account_addr)]
            signer = signer
            t = threading.Thread(target=call_contract, args=(goods_Addr, "Im_goods", "reportGoodsInfo", args, signer))
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        end_time = time.time()
        x_axis.append(concurrency)
        y_axis.append((end_time - start_time) * 1000/concurrency)

    data = {"concurrency level": x_axis,
            "Delay (ms)": y_axis}
    df = pd.DataFrame(data)
    filename = "duoxianc.csv"
    df.to_csv(os.path.join(os.getcwd(), filename), index=False)

    # 绘图
    plt.xticks(range(0, 51, 10))
    plt.bar(x_axis, y_axis, width=7, align='center', alpha=0.5, color=(119/255, 166/255, 234/255))
    plt.xlabel('concurrency level')
    plt.ylabel('Delay (ms)')
    plt.title('Delay Of Report Goods Information')

    # 将图表保存到当前目录下
    filename = "duoxianc.png"
    plt.savefig(os.path.join(os.getcwd(), filename), dpi=400)

    return render_template("container2-1.html", is_login = True, succ_msg = "上报信息成功", container=container, username = username)



