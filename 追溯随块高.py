from flask import request, render_template, session
import traceback
import time

from __init__ import app
from blockchain import call_contract, to_checksum_address
from models import Agency, Contracts, Enterprise, Audit, Engineer, count_numbers
from models import Contracts, Container, Maritime, IPFSObject, db, count_numbers
from client.bcosclient import BcosClient
import matplotlib.pyplot as plt
import os
import pandas as pd


def check_login():
    return session.get("username") is not None


@app.route("/license/<addr>")
def license_handle(addr):
    is_login = check_login()

    try:
        res = call_contract(addr, "License", "getInfo", args=[])
        res2 = call_contract(addr, "License", "showInfo", args=[])
    except Exception:
        traceback.print_exc()
        return render_template("index2.html", is_login=is_login, fail_msg="证书合约地址错误或合约调用失败", count=count_numbers())

    res2 = list(res2)
    license_info = list(res)
    license_info.extend(res2)
    time_local = None
    try:
        time_local = time.localtime(license_info[5] / 1000)
    except Exception:
        traceback.print_exc()
    if time_local is not None:
        license_info[5] = time.strftime("%Y-%m-%d %H:%M:%S", time_local)
    try:
        agency = Agency.query.filter(Agency.contract_addr == license_info[10]).first()
        license_info[10] = agency.username
    except Exception:
        traceback.print_exc()

    try:
        engineer_list = []
        for e_eid in license_info[11]:
            engineer = Engineer.query.filter(Engineer.eid == e_eid).first()
            if engineer is not None:
                engineer_list.append(engineer.username)
            else:
                engineer_list.append(e_eid)
        license_info[11] = engineer_list
    except Exception:
        traceback.print_exc()
    return render_template("license2.html", is_login=is_login, license_info=license_info)


@app.route("/search", methods=["GET", "POST"])
def search():
    is_login = check_login()

    if request.method == "GET":
        return render_template("search2.html", is_login=is_login)

    goodsid = int(request.form.get("goodsid", None))
    if goodsid is None:
        return render_template("search2.html", is_login=is_login, fail_msg="没有查询到货物信息")
    goodsin_Addr = db.session.query(Contracts).filter(Contracts.name == "goods").first().addr

    x_axis = []
    y_axis = []
    y2 = []
    client = BcosClient()
    # 进行 10~100 次 call_contract
    time_list = []
    start_time = time.time()
    for j in range(1,101):

        Goodsdata1 = call_contract(goodsin_Addr, "goods", "filterGoodsInfo",
                                   args=[goodsid])
        if j % 10 == 0:
            end_time = time.time()
            height = client.getBlockNumber()

            x_axis.append(j)
            y_axis.append((end_time - start_time) * 1000 / j)
            y2.append(height)

    # 设置画布大小
    fig = plt.figure(figsize=(10, 6))

    # 绘制柱状图
    ax1 = fig.add_subplot(111)
    ax1.set_xticks(range(0, 101, 10))
    ax1.bar(x_axis, y_axis, width=7, align='center', alpha=0.5, color=(119/255, 166/255, 234/255))
    ax1.set_xlabel('Transaction')
    ax1.set_ylabel('Delay (ms)')
    ax1.set_title('Delay Of Trace')

    # 设置右坐标轴
    ax2 = ax1.twinx()
    ax2.set_ylabel('Block Height')
    ax2.plot(x_axis, y2, '--', color=(240/255, 141/255, 100/255))
    ax2.tick_params(axis='y')
    filename = "zhuisu_kuaigao.png"
    plt.savefig(os.path.join(os.getcwd(), filename), dpi=400)
    client.finish()
    Goodsdata = call_contract(goodsin_Addr, "goods", "filterGoodsInfo",
                              args=[goodsid])
    goodsdata = list(zip(*Goodsdata))

    return render_template("search2.html", is_login=is_login, goodsdata=goodsdata)


@app.route("/report", methods=["GET", "POST"])
def search_report():
    is_login = check_login()

    if request.method == "GET":
        return render_template("report2.html", is_login=is_login)

    goodsid = int(request.form.get("goodsid", None))
    if goodsid is None:
        return render_template("search2.html", is_login=is_login, fail_msg="没有查询到货物信息")

    state_Addr = db.session.query(Contracts).filter(Contracts.name == "state").first().addr

    goodsinfo1 = call_contract(state_Addr, "state", "getTransitionsNoGoodsId1",
                               args=[goodsid])
    goodsinfo2 = call_contract(state_Addr, "state", "getTransitionsNoGoodsId2",
                               args=[goodsid])

    goodsdata1 = list(zip(*goodsinfo1))
    goodsdata2 = list(zip(*goodsinfo2))
    goodsdata = [item1 + item2 for item1, item2 in zip(goodsdata1, goodsdata2)]

    return render_template("report2.html", is_login=is_login, succ_msg="货物状态查询成功", goodsdata=goodsdata)


@app.route("/pubkey", methods=["GET", "POST"])
def public_key():
    is_login = check_login()

    if request.method == "GET":
        return render_template("pubkey2.html", is_login=is_login)

    name = request.form.get("name", None)
    if name is None or name == "":
        return render_template("pubkey2.html", is_login=is_login, fail_msg="输入错误")

    ent_type = request.form.get("ent-type", None)
    if ent_type is None or ent_type not in ["audit", "agency", "enterprise"]:
        return render_template("pubkey2.html", is_login=is_login, fail_msg="实体类型错误")

    if ent_type == "enterprise":
        ent = Enterprise.query.filter(Enterprise.username == name).first()
    elif ent_type == "audit":
        ent = Audit.query.filter(Audit.username == name).first()
    else:
        ent = Agency.query.filter(Agency.username == name).first()

    if ent is None:
        return render_template("pubkey2.html", is_login=is_login, fail_msg="未找到该实体")

    try:
        result = ent.envelope_pub
        if result is None:
            return render_template("pubkey2.html", is_login=is_login, fail_msg="查询失败")
        result = str(result, encoding="utf-8")
    except Exception:
        return render_template("pubkey2.html", is_login=is_login, fail_msg="查询失败")

    return render_template("pubkey2.html", succ_msg="查询成功", is_login=is_login, result=result)


@app.route("/credit", methods=["GET", "POST"])
def credit():
    is_login = check_login()

    if request.method == "GET":
        return render_template("credit2.html", is_login=is_login)

    name = request.form.get("name", None)
    if name is None or name == "":
        return render_template("credit2.html", is_login=is_login, fail_msg="输入错误")

    ent_type = request.form.get("ent-type", None)
    if ent_type is None or ent_type not in ["agency", "engineer"]:
        return render_template("credit2.html", is_login=is_login, fail_msg="实体类型错误")

    if ent_type == "engineer":
        ent = Engineer.query.filter(Engineer.username == name).first()
    else:
        ent = Agency.query.filter(Agency.username == name).first()

    if ent is None:
        return render_template("credit2.html", is_login=is_login, fail_msg="未找到该实体")

    result = None
    try:
        if ent_type == "engineer":

            engineerListAddr = Contracts.query.filter(Contracts.name == "EngineerList").first().addr
            CreditAddr = Contracts.query.filter(Contracts.name == "Credit").first().addr

            # call_contract(engineerListAddr,"EngineerList","getCreditContractAddr", args = [])

            call_contract(engineerListAddr, "EngineerList", "setCreditContractAddr",
                          args=[to_checksum_address(CreditAddr)])

            # call_contract(engineerListAddr,"EngineerList","getCreditContractAddr", args = [])

            call_contract(engineerListAddr, "EngineerList", "updateCredit", args=[ent.eid])
            res = call_contract(engineerListAddr, "EngineerList", "getCredit", args=[ent.eid])
            result = res[0]
        else:
            CreditAddr = Contracts.query.filter(Contracts.name == "Credit").first().addr

            call_contract(ent.contract_addr, "Agency", "setCreditAddr", args=[to_checksum_address(CreditAddr)])
            call_contract(ent.contract_addr, "Agency", "updateCredit", args=[])
            res = call_contract(ent.contract_addr, "Agency", "getCredit", args=[])
            result = res[0]
    except Exception:
        traceback.print_exc()
        return render_template("credit2.html", is_login=is_login, fail_msg="查询失败")
    return render_template("credit2.html", is_login=is_login, succ_msg="查询成功", result=result, name=name)
