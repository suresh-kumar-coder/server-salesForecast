from flask_pymongo import pymongo
from flask import request, jsonify
import certifi
from bson.objectid import ObjectId
import smtplib
from email.message import EmailMessage
from random import randint
import datetime as dt
import pandas as pd
from pandas.errors import ParserError
from dateutil import parser
from prophet import Prophet
import math 
from sklearn.metrics import mean_absolute_error as MAE, mean_squared_error as MSE, mean_absolute_percentage_error as MAPE
import holidays



connection_str = "mongodb+srv://sureshkumarm:OxQdM5AdpkpfZXae@cluster0.b4bhdnb.mongodb.net/?retryWrites=true&w=majority"

client = pymongo.MongoClient(connection_str, tlsCAFile= certifi.where())

db = client.get_database('userdatabase')

user_collection = db['user']
auth_collection = db['auth']
forecast_collection = db['forecast']

def apiRoutes(endpoints):

    @endpoints.route('/register',methods=['POST'])
    def register():
        resp = {}
        status = {}
        data = {}
        
        try:
            email = request.args.get('mail')

            if user_collection.find_one({'mail': email}):
                status = {
                    "statusCode" : '409',
                    "statusMessage" : "User already exists!"
                }
                
            else:
                data["_id"] = str(ObjectId())
                data['username'] = request.args.get('user')
                data['password'] = request.args.get('pass')
                data['mail'] = email

                user_collection.insert_one(data)

                status = {
                    "statusCode" : '200',
                    "statusMessage" : "User data successfully stored!"
                }
                sendMail(email, request.args.get('user'),0)
                resp['data'] = data
                        
        except Exception as e:
            status = {
                "statusCode":"400",
                "statusMessage":str(e)
            }
        
        resp['status'] = status
        return resp
        
    @endpoints.route("/auth",methods=['GET'])
    def authentication():
        response = {}
        email = request.args.get('mail')
        password = request.args.get('pass')

        userData = user_collection.find_one({'mail': email})

        print(userData)

        if userData and userData['password'] == password:
            response['data'] = {
                "token": userData['_id'],
                'username': userData['username'],
                'mail': userData['mail']
            }
            status = {
                "statusCode" : '200',
                "statusMessage" : "Authentication Success!",
            }
            
        elif userData == None:
            status = {
                "statusCode" : '403',
                "statusMessage" : "User not found!"
            }
        
        elif userData['password'] != password:
            status = {
                "statusCode" : '405',
                "statusMessage" : "Password not match"
            }    
        
        response['status'] = status
        return response
    
    @endpoints.route("/forgot",methods=['GET'])
    def forgot():
        resp = {}
        mail = request.args.get("mail")
        if user_collection.find_one({"mail": mail}):
            server = smtplib.SMTP("smtp.gmail.com", 587)

            server.starttls()

            sender = "salesforecastapp@gmail.com"

            pswd = "pzotbzbpdsgailla"

            otp = randint(1000,9999)

            msg = EmailMessage()
            msg['Subject'] = "OTP to change your password!"
            msg['From'] = sender
            msg['To'] = mail
            msg.set_content(f"""    
            Dear recipient,

            Your One Time Password is {otp}.
            
            Enter the OTP in the required field to change your password.
            
            Note that the OTP is vaild for only 120 seconds.

            Regards,
            Sales Forecast App.

            """)


            try: 
                server.login(sender, pswd)
                server.send_message(msg)
                server.quit()
                print("Success")
                user_collection.create_index('expireAt', expireAfterSeconds=120)

                data = {"_id" : str(ObjectId()),
                        'mail': mail,
                        'otp': otp, 
                       'expireAt': dt.datetime.utcnow() + dt.timedelta(minutes=2)}
                auth_collection.insert_one(data)
                status = {
                    "statusCode" : '1',
                    "statusMsg": "otp sent successfully!"
                }

            except Exception as e:
                print(e)
                status = {
                "statusMsg": e
                }
        
        else:
            status = {
                'statusCode': '0',
                "statusMsg": "User not Found!"
            }
        resp['status'] = status
        return resp
    
    @endpoints.route('/otpv', methods=['GET'])
    def otpv():
        resp = {}
        
        mail = request.args.get('mail')
        otp = request.args.get('otp')
        
        try:
            data = auth_collection.find_one({'mail': mail})
            if data['otp'] == int(otp):
               resp['status'] = { 'statusCode' : '1', 
               'statusMsg' : 'OTP Matched'}
            else:
                resp['status'] = { 'statusCode' : '0', 
               'statusMsg' : 'OTP not Matched'}
        except Exception as e:
            resp['status'] = { 'statusCode' : '0', 
               'statusMsg' : e}
            
        return resp
    
    @endpoints.route('/uploaddata', methods=['POST'])
    def uploaddata():
        resp = {}
        flag = int(request.args.get('f'))
        try:
            if flag:
                url = request.form['url']
                print(url, type(url), ".csv" in url)
                if ".csv" in url:
                    df = pd.read_csv(url, sep=";|,")
                else:
                    resp['valid'] = False
                    return resp
            else:
                file = request.files['file']
                df = pd.read_csv(file.stream)
            lst = df.select_dtypes(include=['number']).columns.to_list()
            resp['data'] = lst
            resp['valid'] = len(lst)>0 
            # and find_date_column(df)!= "Not Found"
            print(resp)            
        except ParserError as e:
            resp['error'] = str(e)
            
        return resp
    
    @endpoints.route('/forecast', methods=['POST','GET'])
    def forecast():
        resp = {}
        data = {}
        df2 = pd.DataFrame()
        df3 = pd.DataFrame()
        df4 = pd.DataFrame()
        df5 = pd.DataFrame()
        df6 = pd.DataFrame()
        df7 = pd.DataFrame()
   
        flag = int(request.args.get('f'))
        email = request.args.get('email')

        try:
            if flag:
                url = request.form['url']
                df = pd.read_csv(str(url))
            else:
                file = request.files['file']
                df = pd.read_csv(file.stream)
                date = find_date_column(df) 
                target = request.args.get('target')
                count = int(request.args.get('count'))
                df2[['ds','y']] = df[[date, target]] 
                df2['ds'] = pd.to_datetime(df2['ds']) 
                df2.dropna(inplace=True) 
                if(not frequency(df2)): 
                    df2.set_index('ds', inplace=True)     
                    df3 = df2.resample('D').interpolate()
                    df4['y'] = df3['y']  
                    df4['ds'] = df3.index.values        
                    df4['ds'] = pd.to_datetime(df4['ds'])
                else:
                    df4['ds'] = df2['ds']
                    df4['y'] = df2['y']

                df5 = prophet_(df4,count)
                # df5.to_csv(rf"C:\Users\suresh kumar m\Desktop\Model Output\predicted_csv{randint(1,1000)}.csv")
                
                if(count>14):
                    data['weekly_f'] = 1
                    data['w_yhat'], data['w_e'] = Insight(df5,count,'W') 
                else:
                    data['weekly_f'] = 0
                    
                if(count>60):
                    data['monthly_f'] = 1
                    data['m_yhat'], data['m_e'] = Insight(df5,count,'M') 
                else:
                    data['monthly_f'] = 0
                    
                df6['ds'] = df5['ds']
                df6['ds'] = pd.to_datetime(df6['ds']) 
                df6['y'] = df5['yhat']
                df7 = dailyInsight(df5, len(df4))
                
                if(forecast_collection.find_one({'mail': email})):
                    forecast_collection.delete_one({'mail': email})
                
                data['_id'] = str(ObjectId())
                data['mail'] = email
                data['actual'] = df4.to_dict(orient='records')
                data['pred'] = df6.to_dict(orient='records')
                data['count'] = count
                data['daily'] = df7.to_dict(orient='records')
                # data['image'] = graph1(df4,df5)
                data['stats'] = stats(df4,df5)
                forecast_collection.insert_one(data)
                
                resp['status'] = {
                    'code': 200,
                    'msg': 'success'
                }
                
        except Exception as e:
            resp['Error'] = str(e)
            
        return resp
    
    @endpoints.route('/getforecastdata', methods=["GET"])
    def getforecastdata():
        resp = {}
        mail = request.args.get('email')
        try:
            var = forecast_collection.find_one({'mail':mail})
            if var == None:
                resp['status'] = {
                    'code' : 500,
                    'msg': 'data not found'
                }
            else:
                resp['data'] = forecast_collection.find_one({'mail':mail})
        except Exception as e:
            resp['error'] = str(e)
        return resp
    
    @endpoints.route('/newsletter', methods=['Get'])
    def newsletter():
        mail = request.args.get('mail')
        sendMail(mail,"User",1)
        return {"status": "success"}
    
    return endpoints


"""Supporting Functions"""

def find_date_column(df):
    column = df.columns.to_list()
    for col in column:
        try:
            pd.to_datetime(df[col])
            d = str(df[col][0])
            if (' ' in d or '-' in d or '/' in d ):
                return col
        except Exception as e:
            print(str(e))
            pass
    return "Not Found"
        
def prophet_(data, count):
    model = Prophet()
    model.fit(data)
    f = model.make_future_dataframe(periods= count, freq= "D")
    forecast = model.predict(f)
    return forecast

# def graph1(actual, pred):
#     actual['ds'] = pd.to_datetime(actual['ds'])
#     pred['ds'] = pd.to_datetime(pred['ds'])
#     actual['ds'] = actual['ds'].dt.tz_localize(None)
#     pred['ds'] = pred['ds'].dt.tz_localize(None)
#     fig, ax = plt.subplots()
#     fig.patch.set_alpha(0)
#     sns.lineplot(x=actual['ds'][len(actual)//2:],y=actual['y'][len(actual)//2:], label="actual")
#     sns.lineplot(x=pred['ds'][len(actual):],y=pred['yhat'][len(actual):], label="Prediction")
#     plt.xlabel('Time')
#     plt.ylabel('Sales')
#     plt.title('Sales Forecast')
#     ax.patch.set_alpha(0)
#     random_int = randint(1000,100000)
#     img_url = rf"C:\Users\suresh kumar m\Desktop\salesForecast\src\assets\Forecast_{random_int}.png"
#     plt.savefig(img_url)
#     plt.close()
#     return random_int

def frequency(df):
    diff = []
    for i in range(1,len(df)):
        diff.append(int((df['ds'][i]-df['ds'][i-1]).days))
    val = int(sum(diff)/len(diff))
    res = ''
    if val<7:
        return True
    else:
        return False

def stats(df,pred):
    res = {}
    res['MAE'] = round(MAE(df['y'],pred['yhat'][:len(df)]),2)
    res['MSE'] = round(MSE(df['y'],pred['yhat'][:len(df)]),2)
    res['RMSE'] = round(math.sqrt(res['MSE']),2)
    res['MAPE'] = round(MAPE(df['y'],pred['yhat'][:len(df)])*100,2)
    res['Accuracy'] = 100-res['MAPE']
    return res

def dailyInsight(df, n):
    df1 = pd.DataFrame()
    df1['ds'] = df['ds'][n:n+7]
    df1['y'] = round(df['yhat'][n:n+7],2)
    df1['e'] = None
    df1['e'] = ((df['yhat'] - df['yhat'].shift(1)) / df['yhat'].shift(1)) * 100
    df1['e'] = df1['e'].round(2)
    return df1

def sendMail(mail,user, news):
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    sender = "salesforecastapp@gmail.com"
    pswd = "pzotbzbpdsgailla"
    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = mail
    if(news):
        msg['Subject'] = "Thank You for Subscribing to Our Newsletter!"
        msg.set_content(f"""
Thank you for subscribing to our newsletter! We are delighted to have you as part of our community, and we look forward to sharing valuable insights, updates, and special offers with you.

Regards,
Sales Forecast App.
""")
    else:
        msg['Subject'] = "Welcome to Sales Forecast App - Registration Successful"
        msg.set_content(f"""    
Hello {user},
    
    Congratulations! We are thrilled to inform you that your registration for the Sales Forecast App has been successfully completed. Welcome to our community of users dedicated to accurate sales forecasting and data-driven decision making.
    
    With our app, you now have access to a range of powerful features and tools to optimize your sales forecasting process.\n

    We believe that our Sales Forecast App will greatly benefit your business by enabling you to make data-driven decisions, improve resource planning, and maximize revenue opportunities.\n
    
    To get started, simply log in to the Sales Forecast App using your registered credentials. \n

    Thank you for choosing our Sales Forecast App. We're excited to embark on this forecasting journey with you and support your business growth through accurate sales predictions.\n

    Regards,
    Sales Forecast App.

    """)
    try: 
        server.login(sender, pswd)
        server.send_message(msg)
        server.quit()
        print("Success")
    except Exception as e:
        print(e)        


def Insight(df,count,wm):
    df1 = pd.DataFrame()
    df.set_index(df['ds'],inplace=True)
    df1 = df.resample(wm).mean(numeric_only=True)
    df1.reset_index(drop=True, inplace=True)
    df1['e'] = None
    df1['e'] = ((df1['yhat'] - df1['yhat'].shift(1)) / df1['yhat'].shift(1)) * 100
    df1['e'] = df1['e'].round(2)
    df1['yhat'] = df1['yhat'].round(2)
    if wm=='W':
        x = -(count//7)
    else:
        x = -(count//30)
    return df1['yhat'][x:].to_list(), df1['e'][x:].to_list()
