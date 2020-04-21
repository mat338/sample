# coding:utf-8
import logging
import os
import traceback
import sys
import copy
import datetime
import xlrd  # pip install xlrd
from datetime import datetime, timedelta

# データ作成シート名
CREATE_DATA_SHEET_NAME= u'データ作成'

# 置換データ名一覧(データを増やす場合はここに対象列名を追加すること)
CHANGE_DATA_COL_NO_NAME = [
    u'要因No.', u'DR指示開始日時', u'DR指示期間', u'イベントの状態', u'単位', u'削減電力量', 
    u'DR指示機器ID', u'シーケンス開始番号', u'HEMS機器ID', u'蓄電池機器ID', u'エコキュート機器ID', 
    u'全館空調機器ID_1', u'全館空調機器ID_2', u'積算取得日時', u'瞬間取得日時', u'エネマネステータス', 
    u'オプトアウト作成', u'電力会社ID', u'イベントID', u'更新番号', u'郵便番号', 
    u'全館空調機器ID_1_動作状態詳細', u'全館空調機器ID_1_設定温度', u'全館空調機器ID_2_動作状態詳細', u'全館空調機器ID_2_設定温度',
    u'エコキュート統計データ作成日数', u'郵便番号外気温', u'エコキュート_電力変化', u'全館空調_電力変化', u'登録しないテーブル',
    u'DR参加設定(エコキュート)',u'DR参加設定(全館空調)',u'DR参加設定(蓄電池)',u'DR参加設定(V2H)',u'HEMS機能リスト',u'蓄電池容量',u'メーカーコード(蓄電池)',
    u'規格バージョン(蓄電池)',u'V2H機器ID',u'メーカーコード(V2H)',u'規格バージョン(V2H)'
]

# 読み込み対象外のシート名を記載
NOT_TARGET_SHEET_NAME = [
    u'テスト設計兼結果記録',
    u'要因分析',
    u'基本設定',
    u'設定値',
    CREATE_DATA_SHEET_NAME,
]

# 全館空調対象テーブル
HVAC_TARGET_TABLE = [
    'hvac_centra_results_data',
    'hvac_centra_status',
    'hvac_centra_statistics_minute',
    'hvac_centra_statistics_hour'
]

# delete
delete_sql_str= 'delete from \"public\".{0} where {1};\n'
delete_sql_str_navie= 'delete from \"public\".{0} where {1};\n'
# insert
INSERT_SQL_STR_ENEMANE = 'insert into \"public\".{0} ({1}) VALUES \n'
INSERT_SQL_STR_NAVIE = 'insert into \"public\".{0} ({1}) VALUES\n'

##
#  対象シート名リスト取得
def getTargetSheetNameList(book):
    # Sheet一覧取得
    sheetList= book.sheet_names()

    # 対象シート名を取得
    targetSheetNameList= []
    for sheetName in sheetList:
        if sheetName in NOT_TARGET_SHEET_NAME:
            continue

        # 対象シート名のみ格納
        targetSheetNameList.append(sheetName)

    return targetSheetNameList

##
# 反映テーブル情報取得
def getTableInfoList(targetSheetNameList):
    # シートごとに処理
    tableinfoList= []
    for sheetName in targetSheetNameList:
        # フィールドの初期化
        fieldRowNum= 0
        fieldColNum = 0
        tableinfo= {}
        colNameList= []
        colTypeList= []
        datalist= []

        # シートの読み込み
        tmpSheet= book.sheet_by_name(sheetName)
        # テーブル名を取得
        tableinfo['tableName']= tmpSheet.cell_value(1, 1)
        tableinfo['target']= tmpSheet.cell_value(0, 1)

        # 列名の位置を取得する
        for row in range(1, tmpSheet.nrows):
            for i in range(4):
                if tmpSheet.cell_value(row, i) == u'フィールド名':
                    fieldRowNum= row
                    fieldColNum= i + 1
                    break

            # 取得できていたら処理を抜ける
            if fieldRowNum != 0:
                break

        # フィールド名一覧を取得
        for colNo in range(1, tmpSheet.ncols):
            # 対象列になるまで繰り返し
            if colNo < fieldColNum:
                continue

            # 列名リストを取得
            if tmpSheet.cell_value(fieldRowNum, colNo) != '':
                colNameList.append(tmpSheet.cell_value(fieldRowNum, colNo))
                colTypeList.append(tmpSheet.cell_value(fieldRowNum + 2, colNo))

        # テーブル情報を作成
        tableinfo['colNameList']= colNameList
        tableinfo['colTypeList']= colTypeList
        # 列名にhems_idが存在するか確認
        if u'hems_id' in colNameList:
             tableinfo['existColHemsId']= True
             tableinfo['HemsIdColNo']= colNameList.index(u'hems_id')
        else:
            tableinfo['existColHemsId']= False

        # データを取得
        for row in range(1, tmpSheet.nrows):
            if row < fieldRowNum + 4:
                continue

            data = []
            for colNo in range(1, tmpSheet.ncols):
                # 対象列になるまで繰り返し
                if colNo < fieldColNum:
                    continue

                # 日付型
                if tmpSheet.cell_type(row, colNo) == 3:
                    data.append(
                        str(excel_date(tmpSheet.cell_value(row, colNo))))
                # 数値型
                elif tmpSheet.cell_type(row, colNo) == 2:
                    if tmpSheet.cell_value(row, colNo) != '':
                        data.append(
                            str(tmpSheet.cell_value(row, colNo)).split('.')[0])
                    else:
                        data.append('null')
                else:
                    if tmpSheet.cell_value(row, colNo) != '':
                        data.append(str(tmpSheet.cell_value(row, colNo)))
                    else:
                        data.append('null')
            # 行データ
            datalist.append(data)

        # データを格納
        tableinfo['dataList']=datalist
        tableinfoList.append(tableinfo)

    return tableinfoList


##
# delete文作成
def createDeleteSqlList(tableInfoList):
    # delete文を作成
    allHemsIdList = []
    for tableInfo in tableInfoList:
        deleteSqlList=[]
        # hemsId列が存在する場合
        if tableInfo['existColHemsId'] is True:
            deletehemsIdList=[]
            # delete対象のHemsIDを取得する
            for data in tableInfo['sqlDataList']:
                hemsid=data[tableInfo['HemsIdColNo']]
                if hemsid not in deletehemsIdList:
                    deletehemsIdList.append(hemsid)
                if hemsid not in allHemsIdList:
                    allHemsIdList.append(hemsid)
    
            # delete文
            for tmphemsId in deletehemsIdList:
                if tableInfo['target'] == 'enemane':
                    deleteStr=delete_sql_str.replace('{0}', tableInfo['tableName'])
                    deleteStr=deleteStr.replace('{1}', 'hems_id = \'' + tmphemsId + '\'')
                else:
                    deleteStr=delete_sql_str_navie.replace('{0}', tableInfo['tableName'])
                    deleteStr=deleteStr.replace('{1}', 'hems_id = \'' + tmphemsId + '\'')

                deleteSqlList.append(deleteStr)

            tableInfo['deleteSqlList']=deleteSqlList
        # 時間毎気温予報情報の場合
        elif tableInfo['tableName'] == u'forecast_each_time_temperature_info':
            cityCodeList = []
            for data in tableInfo['sqlDataList']:
                if cityCodeList.count(data[1]):
                   continue

                cityCodeList.append(data[1])
                deleteStr=delete_sql_str.replace('{0}', tableInfo['tableName'])
                deleteStr=deleteStr.replace(
                    '{1}', 'city_code = \'' + data[1] + '\'')
                deleteSqlList.append(deleteStr)

            tableInfo['deleteSqlList']=deleteSqlList

        # DR指示間隔またはオプトアウトステータスの場合
        elif tableInfo['tableName'] == u'dr_event_interval' or tableInfo['tableName'] == u'dr_optout_status':
            for data in tableInfo['sqlDataList']:
                deleteStr=delete_sql_str.replace('{0}', tableInfo['tableName'])
                deleteStr=deleteStr.replace(
                    '{1}', 'vtn_id = \'' + data[0] + '\' and event_id = \'' + data[1] + '\'')
                deleteSqlList.append(deleteStr)

            tableInfo['deleteSqlList']=deleteSqlList

        # hemsId列が存在しない場合(マスタとみなし、TRUNCATEする)
        else:
            tableInfo['deleteSqlList'] = ''
            # tableInfo['deleteSqlList']='TRUNCATE \"public\".' + \
            #     tableInfo['tableName'] + ';\n'

    # HEMSID
    deleteStr = ''
    for hemsId in allHemsIdList:
        for tableName in ['electric_charge_calc_result', 'electric_charge_calc_result', 'load_distribution_control_result', 'ecocute_load_distribution_control', 'hvac_centra_load_distribution_control', 'operation_plan_reduce_demand_response', 'hvac_centra_results_data']:
            deleteStr=deleteStr + delete_sql_str.replace('{0}', tableName)
            deleteStr=deleteStr.replace('{1}', 'hems_id = \'' + hemsId + '\'')           

    return tableInfoList, deleteStr

##
# excelのtime型を変換
def excel_date(num):
    from datetime import datetime, timedelta
    return(datetime(1899, 12, 30) + timedelta(days=num))

##
# insert文作成
def createInsertStr(tableInfoList):
    global INSERT_SQL_STR_ENEMANE
    global INSERT_SQL_STR_NAVIE
    for tableInfo in tableInfoList:
        insertSqlList=[]
        dataStr = ''
        insertSql = ''
        for i, data in enumerate(tableInfo['sqlDataList']):
            if i == 0:
                # 列名の作成
                colnames=','.join(tableInfo['colNameList'])
                if tableInfo['target'] == 'enemane':
                    insertSql = INSERT_SQL_STR_ENEMANE
                else:
                    insertSql = INSERT_SQL_STR_NAVIE

                # テーブル名置換
                insertSql= insertSql.replace('{0}', tableInfo['tableName'])                
                # 列名置換
                insertSql=insertSql.replace('{1}', colnames)

            # データ置換
            datas='\'' + '\',\''.join(data) + '\''
            datas=datas.replace('\'null\'', 'null')
            # 値列の作成
            dataStr=dataStr + '(' + datas + '),\n'


        insertSql = insertSql + dataStr[:-2] + ';\n'
        insertSqlList.append(insertSql)
        tableInfo['insertSqlList']=insertSqlList

    return tableInfoList

##
# 要因No毎に出力
##
# insert文作成
def createInsertStr2(tableInfoList):
    global INSERT_SQL_STR_ENEMANE
    global INSERT_SQL_STR_NAVIE
    for tableInfo in tableInfoList:
        dataStr = ''
        # 要因Noがどこまであるか不明のため、とりあえず100回
        for i in range(100):
            insertSql = ''
            dataStr = ''
            testNo = str(i + 1)
            # 取得できなければ停止
            if testNo not in tableInfo['insertDic']:
                continue

            # 作成対象を取り出し
            insertInfoList = tableInfo['insertDic'][testNo]

            for i, data in enumerate(insertInfoList):
                if i == 0:
                    # 列名の作成
                    colnames=','.join(tableInfo['colNameList'])
                    if tableInfo['target'] == 'enemane':
                        insertSql = INSERT_SQL_STR_ENEMANE
                    else:
                        insertSql = INSERT_SQL_STR_NAVIE

                    # テーブル名置換
                    insertSql= insertSql.replace('{0}', tableInfo['tableName'])                
                    # 列名置換
                    insertSql=insertSql.replace('{1}', colnames)

                # データ置換
                datas='\'' + '\',\''.join(data) + '\''
                datas=datas.replace('\'null\'', 'null')
                # 値列の作成
                dataStr=dataStr + '(' + datas + '),\n'


            insertSql = insertSql + dataStr[:-2] + ';\n'
            tableInfo[testNo] = insertSql

    return tableInfoList

##
# SQL出力
def outputSql(tableInfoList, deleteStr):
    # deleteSql作成
    insertStrEnemane=''
    deleteStrEnemane=''
    insertStrNavie=''
    deleteStrNavie=''

    # 一括で出力
    if isTableSql is False:
        for tableInfo in tableInfoList:
            if tableInfo['target'] == 'enemane':
                insertStrEnemane=insertStrEnemane + \
                    ''.join(tableInfo['insertSqlList'])
                deleteStrEnemane=deleteStrEnemane + \
                    ''.join(tableInfo['deleteSqlList'])
            else:
                insertStrNavie=insertStrNavie + \
                    ''.join(tableInfo['insertSqlList'])
                deleteStrNavie=deleteStrNavie + \
                    ''.join(tableInfo['deleteSqlList'])

        # 削除を追加
        deleteStrEnemane = deleteStrEnemane + deleteStr
        
        # エネマネ用
        f=open(directory + '/insertSqlEnemane.sql', 'w')
        f.write(insertStrEnemane)
        f.close
        f=open(directory + '/deleteSqlEnemane.sql', 'w')
        f.write(deleteStrEnemane)
        f.close

        # ナビエ用
        f=open(directory + '/insertSqlNavie.sql', 'w')
        f.write(insertStrNavie)
        f.close
        f=open(directory + '/deleteSqlNavie.sql', 'w')
        f.write(deleteStrNavie)
        f.close

    else:
        for tableInfo in tableInfoList:
            if tableInfo['target'] == 'enemane':
                # エネマネ用
                f=open(directory + '/enemane_insert_' + \
                       tableInfo['tableName'] + '.sql', 'w')
                f.write(''.join(tableInfo['insertSqlList']))
                f.close
                f=open(directory + '/enemane_delete_' + \
                       tableInfo['tableName'] + '.sql', 'w')
                f.write(''.join(tableInfo['deleteSqlList']))
                f.close
            else:
                # ナビエ用
                # エネマネ用
                f=open(directory + '/Naviehe_insert_' + \
                       tableInfo['tableName'] + '.sql', 'w')
                f.write(''.join(tableInfo['insertSqlList']))
                f.close
                f=open(directory + '/Naviehe_delete_' + \
                       tableInfo['tableName'] + '.sql', 'w')
                f.write(''.join(tableInfo['deleteSqlList']))
                f.close


##
# ケース毎にSQL出力
def outputSql_TestCase(tableInfoList):
    # deleteSql作成
    outputDic = {}
    deleteStr =''

    # 一括で出力
    for tableInfo in tableInfoList:
        # 要因Noがどこまであるか不明のため、とりあえず100回
        for i in range(100):
            insertStr = ''
            testNo = str(i + 1)
            # 取得できなければ停止
            if testNo not in tableInfo:
                continue
            else:
                # 存在する場合は取り出し
                # エネマネ
                if tableInfo['target'] == 'enemane' and testNo in outputDic:
                     insertStr = outputDic[testNo]
                # ナビエ
                if tableInfo['target'] == 'Naviehe' and (testNo + '_N')  in outputDic:
                     insertStr = outputDic[testNo + '_N']
        
            # SQL作成
            insertStr=insertStr +  tableInfo[testNo]
            if tableInfo['target'] == 'enemane':
                outputDic[testNo] = insertStr
            else:
                outputDic[testNo + '_N'] = insertStr

        deleteStr=deleteStr + \
            ''.join(tableInfo['deleteSqlList'])

    for i in range(100):
        testNo = str(i + 1)
        # 取得できなければ停止
        if testNo not in outputDic:
            break

        # エネマネ用
        f=open(directory + '/case_' + testNo + '_enemane_insert.sql', 'w')
        f.write(''.join(outputDic[testNo]))
        f.close

        f=open(directory +  '/case_' + testNo + '_Naviehe_insert.sql', 'w')
        f.write(''.join(outputDic[testNo + '_N']))
        f.close



##
# データ作成用データ取得
def getCreateData():

    # 作成対象bookを取得する
    createBook=xlrd.open_workbook(directory + '/【DR対象判定】create_itdata.xlsx')

    # データ作成シートを取得する
    createDataSheet=createBook.sheet_by_name(CREATE_DATA_SHEET_NAME)

    # データ作成シート読み込み
    # 列名の位置を取得する(対象名称は「要因No.」)
    dataFirstRowNo=-1
    dataFirstColNo=-1
    datainfo={}
    dataList=[]
    colNameList=[]
    indexDict = {}
    isColNameList=False
    cellType=0
    cellValue=''
    tmpValue=''
    for row in range(0, createDataSheet.nrows):
        if dataFirstRowNo == -1:
            for colNo in range(0, createDataSheet.ncols):
                if createDataSheet.cell_value(row, colNo) == u'要因No.':
                    dataFirstRowNo=row
                    dataFirstColNo=colNo
                    break
        # 対象列が取得できた場合、データリストを作成する
        else:
            data=[]
            # データ列名を取得
            for colNo in range(dataFirstColNo, createDataSheet.ncols):
                # 列タイトルがなければ終了
                if createDataSheet.cell_value(dataFirstRowNo, colNo) == '':
                    break;

                # 列名のリストを作成していない場合、作成
                if isColNameList is False:
                    tmpValue = createDataSheet.cell_value(dataFirstRowNo, colNo)
                    colNameList.append(tmpValue)
                    index = CHANGE_DATA_COL_NO_NAME.index(tmpValue)
                    indexDict[CHANGE_DATA_COL_NO_NAME[index]] = colNo 

                # データを詰め込み
                cellType=createDataSheet.cell_type(row, colNo)
                cellValue=createDataSheet.cell_value(row, colNo)
                # 日付型
                if cellType == 3:
                    # 数値で取得できるため、日付型は変換
                    if len(str(excel_date(cellValue))) == 26:
                        data.append(str(excel_date(cellValue))[:-9]  + '00')
                    else:
                        data.append(str(excel_date(cellValue)))
                # 数値型
                elif cellType == 2:
                    if cellValue != '':
                        # 小数を除外
                        data.append(str(cellValue).split('.')[0])
                    else:
                        data.append('null')
                # 文字列型
                else:
                    if cellValue != '':
                        data.append(str(cellValue))
                    else:
                        data.append('null')

            # dataListへ詰め込み
            dataList.append(data)

            # 初回のみ列名を作成
            if isColNameList is False:
                isColNameList=True
                datainfo['colNameList']=colNameList
                datainfo['colIndex'] = indexDict

    # 作成対象列データ格納
    datainfo['dataList']=dataList

    # 対象列が存在しない場合はエラーとする
    if dataFirstRowNo == -1:
        raise Exception('データ作成列が見つけられません。')

    return datainfo

##
#  データ置き変え
def replaceData(tableInfoList, changeDataInfo):
    # データ置換
    changeIndex = changeDataInfo['colIndex']
    changeDataList = changeDataInfo['dataList']
    tableName=''
    prevTestNo = ''
    isTestNoDupulicate = False
    insertDic = {}
    seq = 0

    for changeData in changeDataList:
        # 要因Noを取得
        testNo = changeData[changeIndex[u'要因No.']]

        # シーケンスの初期値を取得
        FIRST_SEQ_NO = changeData[changeIndex[u'シーケンス開始番号']]
        # 積算取得日時の変換(14桁)
        orgSumDateTime = datetime.strptime(changeData[changeIndex[u'積算取得日時']], "%Y-%m-%d %H:%M:%S")
        # 瞬間取得日時の変換(17桁)
        orgReadingDateTime=datetime.strptime(changeData[changeIndex[u'瞬間取得日時']], "%Y-%m-%d %H:%M:%S")

        for tableInfo in tableInfoList:
            testNoSqlDataList = []
            sqlDataList=[]
            tableName=tableInfo['tableName']  

            # 要因番号が前回と同じだったら、DR指示関連のテーブルしか作成しない
            if testNo == prevTestNo:
                if tableName not in ['dr_instruction_info', 'dr_event_interval', 'dr_optout_status']:
                    continue
                else:
                    # 前回作成済みを取り出す
                    if 'insertDic' in tableInfo and testNo in  tableInfo['insertDic']:
                        testNoSqlDataList = tableInfo['insertDic'][testNo]

            # 全館空調がなければ対象テーブルは作成しない
            if tableName in HVAC_TARGET_TABLE and changeData[changeIndex[u'全館空調機器ID_1']] == 'null':
                continue

            # 一度SQLデータを作成済み場合取り出す
            if 'sqlDataList' in tableInfo:
                sqlDataList=tableInfo['sqlDataList']

            # オプトアウト対象か確認する
            if tableName == 'dr_optout_status':
                if changeData[changeIndex[u'オプトアウト作成']] != u'TRUE':
                    continue

            # エコキュート電力変化出力対象か確認する
            if tableName == 'ecocute_power_prediction':
                if changeData[changeIndex[u'エコキュート_電力変化']] != u'TRUE':
                    continue
                    
            # 全館空調_電力変化出力対象か確認する
            if tableName == 'hvac_centra_power_prediction':
                if changeData[changeIndex[u'全館空調_電力変化']] != u'TRUE':
                    continue

            # データを置き換えて作成する
            seq = int(FIRST_SEQ_NO)
            for i, data in enumerate(tableInfo['dataList']):
                # dataをコピーする
                tmpCopy=copy.deepcopy(data)

                # 同一テストNoだった場合、DR指示関連だけ作成する
                # SEQ_NOの変換
                if u'seq_no' in tableInfo['colNameList']:
                    tmpCopy[tableInfo['colNameList'].index('seq_no')] = str(seq)
                    seq = seq + 1

                # 郵便番号
                if u'prefecture_code' in tableInfo['colNameList']:
                    tmpCopy[tableInfo['colNameList'].index('prefecture_code')] = changeData[changeIndex[u'郵便番号']]
                if u'city_code' in tableInfo['colNameList']:
                   tmpCopy[tableInfo['colNameList'].index('city_code')] = changeData[changeIndex[u'郵便番号']]
                if u'postal_code' in tableInfo['colNameList']:
                    tmpCopy[tableInfo['colNameList'].index('postal_code')] = changeData[changeIndex[u'郵便番号']]
                
                # 時間毎気温予報情報かつ郵便番号外気温が入力されている場合、設定温度を変更する。
#                if tableName == u'forecast_each_time_temperature_info' and changeData[changeIndex[u'郵便番号外気温']] != 'null':
#                    tmpCopy[tableInfo['colNameList'].index('temperature')] = changeData[changeIndex[u'郵便番号外気温']]

                # 瞬間取得日時(17桁)
                if u'current_reading_time' in tableInfo['colNameList']:
                    # 30分単位または１時間単位
                    # とりあえず、30分単位
                    # 計算対象外だった場合は計算しない
                    if tableName in ['connect_master_info_status', 'forecast_each_time_temperature_info']:
                        tmptime = orgReadingDateTime
                    else:
                        tmptime = orgReadingDateTime - timedelta(minutes = (30 * i))
                        
                    tmpCopy[tableInfo['colNameList'].index(
                        'current_reading_time')]=tmptime.strftime("%Y%m%d%H%M%S") + "000"

                # 積算取得日時(14桁)
                if u'sum_reading_time' in tableInfo['colNameList']:
                    # テーブル名に「minute」が入っている場合は30分単位
                    if tableName.count('minute'):
                        tmptime = orgSumDateTime - timedelta(minutes = (30 * i))
                        tmpCopy[tableInfo['colNameList'].index(
                            'sum_reading_time')]=tmptime.strftime("%Y%m%d%H%M%S")
                    # 他は１時間単位
                    else:
                        tmptime = orgSumDateTime - timedelta(hours = (1 * i))
                        tmpCopy[tableInfo['colNameList'].index(
                            'sum_reading_time')]=tmptime.strftime("%Y%m%d%H%M%S")

                # 接続機器設定_HEMSステータスの設定変更
                if tableName == u'equipment_setting_status':
                    # エコキュート
                    if changeData[changeIndex[u'エコキュート機器ID']] != 'null':
                        tmpCopy[tableInfo['colNameList'].index('ecocute')]='ON'
                    else:
                        tmpCopy[tableInfo['colNameList'].index(
                            'ecocute')]='OFF'
                    # 全館空調
                    if changeData[changeIndex[u'全館空調機器ID_1']] != 'null' or changeData[changeIndex[u'全館空調機器ID_2']] != 'null':
                        tmpCopy[tableInfo['colNameList'].index('hvac')]='ON'
                    else:
                        tmpCopy[tableInfo['colNameList'].index('hvac')]='OFF'

                # HEMS_IDの変換
                if tableInfo['existColHemsId'] is True:
                    tmpCopy[tableInfo['HemsIdColNo']
                        ]=changeData[changeIndex[u'HEMS機器ID']]

                
                # エコキュート機器IDの変換
                if u'id' in tableInfo['colNameList'] and tmpCopy[tableInfo['colNameList'].index('id')] == 'ECOQ____002' :
                    tmpCopy[tableInfo['colNameList'].index('id')] = changeData[changeIndex[u'エコキュート機器ID']]

                # 電力会社ID
                if u'vtn_id' in tableInfo['colNameList']:
                    tmpCopy[tableInfo['colNameList'].index('vtn_id')] = changeData[changeIndex[u'電力会社ID']]

                # イベントID
                if u'event_id' in tableInfo['colNameList']:
                    tmpCopy[tableInfo['colNameList'].index('event_id')] = changeData[changeIndex[u'イベントID']]

                # 更新番号
                if u'modification_number' in tableInfo['colNameList']:
                    tmpCopy[tableInfo['colNameList'].index('modification_number')] = changeData[changeIndex[u'更新番号']]
    

                # DR指示情報の変換
                if tableName == u'dr_instruction_info':
                    # DR開始日時
                    tmpCopy[tableInfo['colNameList'].index('start_date_time')]=changeData[changeIndex[u'DR指示開始日時']]
                    # DR指示期間
                    tmpCopy[tableInfo['colNameList'].index('duration')]=changeData[changeIndex[u'DR指示期間']]
                    # イベントの状態
                    tmpCopy[tableInfo['colNameList'].index('event_status')]=changeData[changeIndex[u'イベントの状態']]
                    # 値のスケール
                    tmpCopy[tableInfo['colNameList'].index('scale_code')]=changeData[changeIndex[u'単位']]
                    # 機器ID
                    tmpCopy[tableInfo['colNameList'].index('device_id')]=changeData[changeIndex[u'DR指示機器ID']]
                    # エネマネステータス
                    tmpCopy[tableInfo['colNameList'].index('enemane_status')]=changeData[changeIndex[u'エネマネステータス']]

                # DR指示間隔
                if tableName == u'dr_event_interval':
                    # DR指示期間
                    tmpCopy[tableInfo['colNameList'].index('duration')]=changeData[changeIndex[u'DR指示期間']]
                    # 削減電力量
                    tmpCopy[tableInfo['colNameList'].index('dr_value')]=changeData[changeIndex[u'削減電力量']]

                # 電力使用量調整協力設定_HEMSステータス
                if tableName == u'power_adjust_join_setting_status':
                    # エコキュート
                    tmpCopy[tableInfo['colNameList'].index('ecocute')]=changeData[changeIndex[u'DR参加設定(エコキュート)']]
                    # 全館空調
                    tmpCopy[tableInfo['colNameList'].index('hvac')]=changeData[changeIndex[u'DR参加設定(全館空調)']]
                    # 蓄電池
                    tmpCopy[tableInfo['colNameList'].index('accumulator')]=changeData[changeIndex[u'DR参加設定(蓄電池)']]
                    # V2H
                    tmpCopy[tableInfo['colNameList'].index('ev_charge_discharger')]=changeData[changeIndex[u'DR参加設定(V2H)']]

                # HEMS_機器情報_HEMS_ECU_インフォ
                if tableName == u'hems_info':
                    # HEMS機能リスト
                    tmpCopy[tableInfo['colNameList'].index('function_list')]=changeData[changeIndex[u'HEMS機能リスト']]

                # 蓄電池_統計データ(分単位)
                if tableName == u'accumulator_statistics_minute':
                    # 機器ID
                    tmpCopy[tableInfo['colNameList'].index('id')]=changeData[changeIndex[u'蓄電池機器ID']]

                # 蓄電池_HEMSステータス
                if tableName == u'accumulator_status':
                    # 機器ID
                    tmpCopy[tableInfo['colNameList'].index('id')]=changeData[changeIndex[u'蓄電池機器ID']]

                    # 蓄電池容量
                    tmpCopy[tableInfo['colNameList'].index('accumulator_capacity')]=changeData[changeIndex[u'蓄電池容量']]

                # EL機器基本情報-接続情報
                if tableName == u'echonet_lite_connect_info':
                    # メーカーコード
                    tmpCopy[tableInfo['colNameList'].index('manufacturer_code')]=changeData[changeIndex[u'メーカーコード(蓄電池)']]
                    # 規格バージョン
                    tmpCopy[tableInfo['colNameList'].index('standard_version_infomation')]=changeData[changeIndex[u'規格バージョン(蓄電池)']]
                	                
                # 全館空調HEMSステータス
                if tableName == u'hvac_centra_status':
                    # 動作状態詳細が入っている場合
                    if changeData[changeIndex[u'全館空調機器ID_1_動作状態詳細']] != 'null':
                         tmpCopy[tableInfo['colNameList'].index('details_device_status')] = \
                            changeData[changeIndex[u'全館空調機器ID_1_動作状態詳細']]

                    # 設定温度が入っている場合変更
                    if changeData[changeIndex[u'全館空調機器ID_1_設定温度']] != 'null':
                         tmpCopy[tableInfo['colNameList'].index('hvac_conf')] = \
                            changeData[changeIndex[u'全館空調機器ID_1_設定温度']]

                testNoSqlDataList.append(tmpCopy)
                sqlDataList.append(tmpCopy)

                # EL機器基本情報-接続情報テーブルかつ、メーカーコード(V2H)又は規格バージョン(V2H)が入っていた場合、機器IDをV2H用に変更してレコード追加
                if tableName == u'echonet_lite_connect_info' and (changeData[changeIndex[u'メーカーコード(V2H)']] != 'null' or changeData[changeIndex[u'規格バージョン(V2H)']] != 'null'):
                    tmpCopy2 = copy.deepcopy(tmpCopy)

                    # 機器ID
                    tmpCopy2[tableInfo['colNameList'].index('id')] = changeData[changeIndex[u'V2H機器ID']]
                    # メーカーコード(V2H)
                    tmpCopy2[tableInfo['colNameList'].index('manufacturer_code')] = changeData[changeIndex[u'メーカーコード(V2H)']]
                    # 規格バージョン(V2H)
                    tmpCopy2[tableInfo['colNameList'].index('standard_version_infomation')] = changeData[changeIndex[u'規格バージョン(V2H)']]
                    # シーケンスNo.
                    if 'seq_no' in tableInfo['colNameList']:
                        tmpCopy2[tableInfo['colNameList'].index('seq_no')] = str(seq)
                        seq = seq + 1

                    sqlDataList.append(tmpCopy2)
                    testNoSqlDataList.append(tmpCopy2)

                # 全館空調対象テーブルかつ、全館空調機器ID_2が入っていた場合、機器IDを変更して追加
                if tableName in HVAC_TARGET_TABLE and changeData[changeIndex[u'全館空調機器ID_2']] != 'null':
                    tmpCopy2 = copy.deepcopy(tmpCopy)

                    # 全館空調HEMSステータス
                    if tableName == u'hvac_centra_status':
                        # 動作状態詳細が入っている場合
                        if  changeData[changeIndex[u'全館空調機器ID_2_動作状態詳細']] != 'null':
                            tmpCopy2[tableInfo['colNameList'].index('details_device_status')] = \
                                changeData[changeIndex[u'全館空調機器ID_2_動作状態詳細']]

                        # 設定温度が入っている場合変更
                        if  changeData[changeIndex[u'全館空調機器ID_2_設定温度']] != 'null':
                            tmpCopy2[tableInfo['colNameList'].index('hvac_conf')] = \
                                changeData[changeIndex[u'全館空調機器ID_2_設定温度']]

                    # 機器ID
                    tmpCopy2[tableInfo['colNameList'].index('id')] = changeData[changeIndex[u'全館空調機器ID_2']]
                    # シーケンスNo.
                    if 'seq_no' in tableInfo['colNameList']:
                        tmpCopy2[tableInfo['colNameList'].index('seq_no')] = str(seq)
                        seq = seq + 1

                    sqlDataList.append(tmpCopy2)
                    testNoSqlDataList.append(tmpCopy2)

                # エコキュート統計データ(分)
                if tableName == u'ecocute_statistics_minute':
                    # エコキュート統計データ作成日数が入っている場合、指定された日数分作成する
                    if changeData[changeIndex[u'エコキュート統計データ作成日数']] != 'null':
                        createDay = int(changeData[changeIndex[u'エコキュート統計データ作成日数']]) - 1
                        for j in range(createDay):
                            tmpCopy2 = copy.deepcopy(tmpCopy)
                            tmptime2 = tmptime -  timedelta(days = (1 * j + 1))
                            tmpCopy2[tableInfo['colNameList'].index(
                              'sum_reading_time')]=tmptime2.strftime("%Y%m%d%H%M%S")   
                            sqlDataList.append(tmpCopy2)     
                            testNoSqlDataList.append(tmpCopy2)  

            tableInfo['sqlDataList']=sqlDataList
 
            # 要因毎に格納
            if 'insertDic' in tableInfo:
                insertDic = tableInfo['insertDic']
                insertDic[testNo] = testNoSqlDataList
                tableInfo['insertDic'] = insertDic
            else:
                insertDic = {}
                insertDic[testNo] = testNoSqlDataList
                tableInfo['insertDic'] = insertDic

        # 前回と同じ要因Noが違った場合、格納
        if testNo != prevTestNo:
            prevTestNo = testNo

    return tableInfoList

##
# メイン処理
if __name__ == "__main__":
    try:
        # コマンドライン引数取得
        args=sys.argv
        isTableSql=False
        fileName=''

        # 引数確認
        if args:
            fileName=args[0]
            if len(args) > 1:
                isTableSql=True


        # 元データBook取得
        directory=os.path.dirname(os.path.abspath(__file__))
        book=xlrd.open_workbook(directory + '/【DR対象判定】create_itdata.xlsx')

        # 対象リストを取得
        targetSheetNameList=getTargetSheetNameList(book)

        # テーブル情報リスト取得
        tableInfoList=getTableInfoList(targetSheetNameList)

        # 変換作成データ取得
        changeDataInfo=getCreateData()

        # データ置換
        tableInfoList=replaceData(tableInfoList, changeDataInfo)

        # delete作成
        tableInfoList, deleteStr =createDeleteSqlList(tableInfoList)

        # insert作成
        tableInfoList=createInsertStr(tableInfoList)
        # insert作成
        tableInfoList=createInsertStr2(tableInfoList)

        # SQL出力
        outputSql(tableInfoList, deleteStr)
        outputSql_TestCase(tableInfoList)

        book=None
        createBook=None
        directory=None

        print('正常に終了しました。')

    except Exception as e:
        traceback.print_exc()
