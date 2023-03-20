import os
import random
import smtplib
from datetime import datetime, timedelta
from random import randrange
from uuid import uuid4
import sys
from functools import wraps
import pymongo as mongo
from bson.objectid import ObjectId
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()  # take environment variables from .env.


"""
█▀▄▀█ █▀▀█ █▀▀▄ █▀▀▀ █▀▀█ 
█░▀░█ █░░█ █░░█ █░▀█ █░░█ 
▀░░░▀ ▀▀▀▀ ▀░░▀ ▀▀▀▀ ▀▀▀▀
"""
MONGO_USERNAME = os.environ.get("MONGO_USERNAME")
MONGO_PASSWORD = os.environ.get("MONGO_PASSWORD")
url = f"mongodb://{MONGO_USERNAME}:{MONGO_PASSWORD}@trailcluster-shard-00-00.dhfoi.mongodb.net:27017,trailcluster-shard-00-01.dhfoi.mongodb.net:27017,trailcluster-shard-00-02.dhfoi.mongodb.net:27017/myFirstDatabase?ssl=true&replicaSet=atlas-jab1mb-shard-0&authSource=admin&retryWrites=true&w=majority"
client = mongo.MongoClient(url)

"""
█▀▀ █░░ █▀▀█ █▀▀ █░█ 
█▀▀ █░░ █▄▄█ ▀▀█ █▀▄ 
▀░░ ▀▀▀ ▀░░▀ ▀▀▀ ▀░▀
"""
app = Flask(__name__)
CORS(app, resources={r"*": {"origins": "*"}})
app.config['CORS_HEADERS'] = 'Content-Type, Access-Control-Allow-Origin'

@app.route("/", methods=["GET"])
def main():
	return jsonify({
		"message": "Working"
	}), 200



"""
█▀▀ █░░█ █▀▀▄ █▀▀ ▀▀█▀▀ ░▀░ █▀▀█ █▀▀▄ █▀▀ 
█▀▀ █░░█ █░░█ █░░ ░░█░░ ▀█▀ █░░█ █░░█ ▀▀█ 
▀░░ ░▀▀▀ ▀░░▀ ▀▀▀ ░░▀░░ ▀▀▀ ▀▀▀▀ ▀░░▀ ▀▀▀
"""
def auth_required(func):
	@wraps(func)
	def authenticator(*args, **kwargs):
		try:
			sid = request.headers.get("WWW-Authenticate")
			db = client["users"]
			sessions_collection = db["sessions"]
			sid_document = sessions_collection.find_one({"sid": sid})
			if sid_document != None:
				expired = sid_document["expiry"] > datetime.today().replace(microsecond=0)
				if expired != False:
					return func(*args, **kwargs)
			return jsonify({
				"message": "Auth failed"
			}), 401
		except Exception as e:
			print(e)
			return jsonify({
				"message": "Oops! Something went wrong during auth"
			}), 500
	return authenticator


def uuid_generator():
	uuid_1 = uuid4().hex
	uuid_2 = uuid4().hex
	return "".join(random.sample(uuid_1+uuid_2, len(uuid_1+uuid_2)))

def mail_otp(to):
	SENDER_GMAIL = os.environ.get("SENDER_GMAIL")
	SENDER_GMAIL_KEY = os.environ.get("SENDER_GMAIL_KEY")
	otp = str(randrange(100000, 999999))
	mail_content = f"""
	Hello,
	OTP: {otp}
	"""
	s = smtplib.SMTP('smtp.gmail.com', 587)
	s.starttls()
	s.login(SENDER_GMAIL, SENDER_GMAIL_KEY)
	s.sendmail(from_addr=SENDER_GMAIL, to_addrs=to, msg=mail_content)
	return True, otp

def update_stats(status):
	try:
		db = client["users"]
		stats_collection = db["stats"]
		today = datetime.today().replace(minute=0, hour=0, second=0, microsecond=0)
		today_collection = stats_collection.find_one({"date": today})
		if today_collection != None:
			stats_collection.update_one(
				{"date": today},
				{"$set": {status: today_collection[status]+1}}
			)
		else:
			last_date_collection = list(stats_collection.find().sort("date", -1).limit(1))[0]
			diff = (today - last_date_collection["date"]).days
			for day in range(1, diff):
				filler_stats = {
					"date": last_date_collection["date"] + timedelta(days=day),
					"confirmed": 0,
					"created": 0,
					"pending": 0,
					"rejected": 0,
					"workinprogress": 0
				}
				stats_collection.insert_one(filler_stats)
			today_stat = {
					"date": today,
					"confirmed": 0,
					"created": 0,
					"pending": 0,
					"rejected": 0,
					"workinprogress": 0					
			}
			today_stat[status] += 1
			stats_collection.insert_one(today_stat)
		return True
	except Exception as e:
		print(e)
		return False

def signup_func(user_details):
	db = client["users"]
	userDetails_collection = db["userDetails"]
	if (userDetails_collection.find_one({"phone": user_details["phone"]}) != None) and (userDetails_collection.find_one({"mail": user_details["mail"]}) != None) :
		return jsonify({
			"message": "This phone number already has an account associated with it"
		}), 200
	otp_status, otp = mail_otp(user_details["mail"])
	if otp_status == True:
		user_details["otp"] = otp
		user_details["otp_expiry"] = datetime.today().replace(microsecond=0) + timedelta(minutes=2)
		user_details["otp_verified"] = False
		userDetails_collection.insert_one(user_details)
		return jsonify({
			"message": f"OTP has been sent to {user_details['mail']}"
		}), 200
	elif otp_status == False:
		return jsonify({
			"message": "Something wrong with OTP! Check mail address"
		}), 422

def otp_verification_func(phone, otp):
	db = client["users"]
	userDetails_collection = db["userDetails"]
	user = userDetails_collection.find_one({"phone": phone})
	if user != None:
		otp_time = datetime.today().replace(microsecond=0)
		if otp_time < user["otp_expiry"]:
			if user["otp"] == otp:
				userDetails_collection.update_one({"phone": phone}, {"$set": {"otp_verified": True, "isLoggedIn": True}, "$unset": {"otp": 1, "otp_expiry": 1}})
				return jsonify({
					"message": "OTP verified"
				}), 200
			else:
				return jsonify({
					"message": "OTP does not match"
				}), 401
		else:
			return jsonify({
				"message": "OTP expired"
			}), 401
	else:
		return jsonify({
			"message": "User not found"
		}), 404

def login_func(phone, password):
	db = client["users"]
	userDetails_collection = db["userDetails"]
	user = userDetails_collection.find_one({"phone": phone})
	if user != None:
		if user["phone"] == phone and user["password"] == password:
			login_id = uuid_generator()
			userDetails_collection.update_one({"phone": phone}, {"$set": {"login_id": login_id, "isLoggedIn": True}})
			return jsonify({
				"login_id": login_id,
				"message": "Log in success"
			}), 200
		else:
			return jsonify({
				"message": "Credentials do not match"
			}), 401
	else:
		return jsonify({
				"message": "User not found"
			}), 404

def userinfo_func(phone):
	db = client["users"]
	userDetails_collection = db["userDetails"]
	user = userDetails_collection.find_one({"phone": phone})
	if user != None:
		user["_id"] = str(user["_id"])
		return jsonify({
			"message": "User details",
			"user_details": user
		}), 200
	else:
		return jsonify({
			"message": "User not found"
		}), 404

def userposts_func(phone, page):
	try:
		db = client["users"]
		posts_collection = db["posts"]
		posts = posts_collection.find({"phone": phone})
		user_posts_lst = []
		for post in posts:
			post["_id"] = str(post["_id"])
			user_posts_lst.append(post)
		limit = 10
		start = page * limit
		posts_to_send = user_posts_lst[start: start+limit]
		for i in range(len( posts_to_send)):
			if(posts_to_send[i]['image'])==[""]: #code to change image if empty to empty list
				posts_to_send[i]['image']=[]
		return jsonify({
			"message": "Posts",
			"next_url": f"?page={page+1}",
			"prev_url": f"?page={page-1}",
			"posts": posts_to_send
		}), 200
	except Exception as e:
		print(e)
		return jsonify({
			"error": e,
			"message": "Oops! Something went wrong"
		}), 500

def accountedit_func(username, phone):
	try:
		db = client["users"]
		userDetails_collection = db["userDetails"]
		userDetails_collection.update_one({"phone": phone}, { "$set": {"name": username}})
		return jsonify({
			"message": "User info updated"
		}), 200
	except Exception as e:
		print(e)
		return jsonify({
			"error": e,
			"message": "Oops! Something went wrong"
		}), 500

def forgotpassword_func(phone):
	db = client["users"]
	userDetails_collection = db["userDetails"]
	user = userDetails_collection.find_one({"phone": phone})
	mail = user["mail"]
	otp_status, otp = mail_otp(mail)
	userDetails_collection.update_one(
		{"phone": phone},
		{"$set": {"otp": otp, "otp_expiry": datetime.today().replace(microsecond=0) + timedelta(minutes=2), "isLoggedIn": False}}
	)
	return jsonify({
			"message": f"OTP has been sent to {mail}"
		}), 200

def changepassword_func(phone, otp, password):
	db = client["users"]
	userDetails_collection = db["userDetails"]
	user = userDetails_collection.find_one({"phone": phone})
	otp_time = datetime.today().replace(microsecond=0)
	if otp_time < user["otp_expiry"]:
		if user["otp"] == otp:
			userDetails_collection.update_one(
					{"phone": phone},
					{"$set": {"password": password}, "$unset": {"otp": 1, "otp_expiry": 1}}
				)
			return jsonify({
					"message": "Password changed successfully"
				}), 200
		else:
			return jsonify({
					"message": "OTP does not match"
				}), 401
	else:
		return jsonify({
				"message": "OTP expired"
			}), 401

def uploadpost_func(title, description, images, category, phone, lat, lon, address, taluk):
	try:
		db = client["users"]
		posts_collection = db["posts"]
		userDetails_collection = db["userDetails"]
		images_lst = [i for i in images.split(",")]
		post_details = {
			"title": title,
			"description": description,
			"image": images_lst,
			"category": category,
			"phone": phone,
			"location": {
				"lat": lat,
				"lon": lon,
				"address": address,
				"taluk": taluk
			},
			"postedOn": datetime.today().replace(microsecond=0),
			"lastUpdated": datetime.today().replace(microsecond=0),
			"status": "Pending",
			"likes": 0,
			"likedBy": []
		}
		post = posts_collection.insert_one(post_details)
		pid = str(post.inserted_id)
		userDetails_collection.update_one({"phone": phone}, {"$push": {"posts": pid}})
		tokenid = category[:4] + "-" + phone[5:] + "-" + pid[10:]
		posts_collection.update_one({"_id": ObjectId(pid)}, {"$set": {"tokenid": tokenid}})
		update_stats("created")
		return jsonify({
			"message": "Post uploaded successfully"
		}), 200
	except Exception as e:
		print(e)
		return jsonify({
			"error": e,
			"message": "Oops! Something went wrong"
		}), 500

def dept_transfer(pid, department):
	db = client["users"]
	posts_collection = db["posts"]
	posts_collection.update_one({"_id": ObjectId(pid)}, {"$set": {"department": department}})
	return jsonify({
		"message": "Post updated"
	}), 200

def getposts_func(page):
	try:
		db = client["users"]
		posts_collection = db["posts"]
		posts = []
		for post in posts_collection.find():
			post["_id"] = str(post["_id"])
			posts.append(post)
		limit = 10
		start = page * limit
		posts_to_send = posts[start: start + 30]
		prev_url = ""
		if page > 0:
			prev_url = page - 1
		next_url = ""
		if len(posts) > start + 30:
			next_url = page + 1
		for i in range(len( posts_to_send)):
			if(posts_to_send[i]["image"]) == [""]: #code to change image if empty to empty list
				posts_to_send[i]["image"] = []	
		return jsonify({
				"message": "Posts",
				"next_url": next_url,
				"prev_url": prev_url,
				"posts": posts_to_send
			}), 200
	except Exception as e:
		print(e)
		return jsonify({
			"error": e,
			"message": "Oops! Something went wrong"
		}), 500

def departmentsprobs_func(dept):
	db = client["users"]
	departments_collection = db["departments"]
	dept = departments_collection.find_one({"name": dept})
	if dept != None:
		problems_lst = dept["problems"]
		return jsonify({
				"message": "List of probs",
				"problems": problems_lst
			}), 200
	else:
		return jsonify({
				"message": f"No such department found! Available departments: {[dept['name'] for dept in departments_collection.find()]}"
			}), 404

def departments_func():
	db = client["users"]
	departments_collection = db["departments"]
	dept_lst = []
	for dept in departments_collection.find():
		dept["_id"] = str(dept["_id"])
		dept_lst.append(dept)
	return jsonify({
			"message": "List of depts",
			"departments": dept_lst
		}), 200

def like_func(phone, pid):
	db = client["users"]
	posts_collection = db["posts"]
	userDetails_collection = db["userDetails"]
	post = posts_collection.find_one({"_id": ObjectId(pid)})
	user = userDetails_collection.find_one({"phone": phone})
	if post == None:
		return jsonify({
				"message": "Post not found"
			}), 404
	elif user == None:
		return jsonify({
				"message": "User not found"
			}), 404
	else:
		if user["isLoggedIn"] == True:
			likes = post["likes"] + 1
			posts_collection.update_one(
				{"_id": ObjectId(pid)},
				{
					"$set": {"likes": likes},
					"$push": {"likedBy": phone}
				}
			)
			userDetails_collection.update_one(
				{"phone": phone},
				{
					"$push": {"likedPosts": pid}
				}
			)
			return jsonify({
					"message": "Post liked successfully"
				}), 200
		elif user["isLoggedIn"] == False:
			return jsonify({
				"message": "The user is not logged in"
			}), 401

def logout_func(phone, login_id):
	db = client["users"]
	userDetails_collection = db["userDetails"]
	if userDetails_collection.find_one({"phone": phone, "login_id": login_id}) != None:
		userDetails_collection.update_one({"phone": phone}, {"$set": {"login_id": None, "isLoggedIn": False}})
		return jsonify({
			"message": "Log out success"
		}), 200
	else:
		return jsonify({
			"message": "Sign out failed | Phone and/or login_id wrong"
		}), 422

def adminlogin_func(mail, password, ip):
	db = client["users"]
	collection = db["adminDetails"]
	sessions_collection = db["sessions"]
	admin = collection.find_one({"mail": mail})
	existing_session = sessions_collection.find_one({"ip": ip})
	if admin != None:
		if existing_session == None:
			if admin["mail"] == mail and admin["password"] == password:
				sid = uuid_generator()
				expiry = datetime.today().replace(microsecond=0) + timedelta(hours=24)
				sessions_collection.insert_one(
					{
						"sid": sid,
						"mail": mail,
						"expiry": expiry,
						"start": datetime.today().replace(microsecond=0),
						"ip": ip
					}
				)
				return jsonify({
					"message": "Log in success",
					"sid": sid,
					"expiry": expiry
				}), 200
			else:
				return jsonify({
					"message": "Credentials does not match"
				}), 401
		else:
			sid = existing_session["sid"]
			adminlogout_func(sid)
			return adminlogin_func(mail, password, ip)
	else:
		return jsonify({
			"message": "User not found"
		}), 404

def sidcheck_func(sid):
	db = client["users"]
	admin_collection = db["adminDetails"]
	sessions_collection = db["sessions"]
	session = sessions_collection.find_one({"sid": sid})
	if session != None:
		admin = admin_collection.find_one({"mail": session["mail"]})
		if session["expiry"] > datetime.today().replace(microsecond=0):
			return jsonify({
				"message": "User details",
				"isLoggedIn": True,
				"email": admin["mail"],
				"role": admin["role"],
				"expiry": session["expiry"]
			}), 200
		else:
			return jsonify({
				"message": "SID expired"
			}), 401
	else:
		return jsonify({
			"message": "User not found"
		}), 404

def admingetposts_func(page):
	try:
		db = client["users"]
		posts_collection = db["posts"]
		posts = []
		for post in posts_collection.find():
			post["_id"] = str(post["_id"])
			posts.append(post)
		limit = 30
		start = page * limit
		posts_to_send = posts[start: start + 30]
		prev_url = ""
		if page > 0:
			prev_url = page - 1
		next_url = ""
		if len(posts) > start + 30:
			next_url = page + 1
		for i in range(len( posts_to_send)):
			if(posts_to_send[i]["image"]) == [""]: #code to change image if empty to empty list
				posts_to_send[i]["image"] = []	
		return jsonify({
				"message": "Posts",
				"next_url": next_url,
				"prev_url": prev_url,
				"posts": posts_to_send
			}), 200
	except Exception as e:
		print(e)
		return jsonify({
				"error": e,
				"message": "Oops! Something went wrong"
			}), 500

def editpost_func(to_update, pid):
	db = client["users"]
	posts_collection = db["posts"]
	post = posts_collection.find_one({"_id": ObjectId(pid)})
	if post != None:
		if to_update.get("status"):
			if to_update["status"] not in ["confirmed", "workinprogress", "created", "rejected", "pending","completed"]:
				return jsonify({
						"message": "Status field should be any of the following fields only: [confirmed, workinprogress, created, rejected, pending, completed]"
					}), 422
			stats_update_status = update_stats(to_update["status"])
		posts_collection.update_one(
				{"_id": ObjectId(pid)},
				{"$set": to_update}
			)
		posts_collection.update_one(
				{"_id": ObjectId(pid)},
				{"$set":{"lastUpdated": datetime.today().replace(microsecond=0)}}
			)
		return jsonify({
			"message": "Status updated successfully"	
		}), 200
	else:
		return jsonify({
			"message": "Post not found"
		}), 404

def stats_func():
	db = client["users"]
	stats_collection = db["stats"]
	week_stats = stats_collection.find().sort("_id", -1).limit(7)
	week_stats_lst = []
	for doc in week_stats:
		del doc["_id"]
		week_stats_lst.append(doc)
	return jsonify({
			"message": "Stats",
			"stats": week_stats_lst
		}), 200

def monthinfo_func():
	try:
		db = client["users"]
		stats_collection = db["stats"]
		today = datetime.today().replace(minute=0, hour=0, second=0, microsecond=0)
		start = today.replace(day=1)
		print(today, start)
		this_month_documents = stats_collection.find({
			"date": {
				"$gte": start,
				"$lte": today
			}
		})
		res = {
			"month": today.strftime("%m"),
			"confirmed": 0,
			"created": 0,
			"pending": 0,
			"rejected": 0,
			"workinprogress": 0
		}
		for day in this_month_documents:
			for status, count in day.items():
				if status in ["_id", "date"]:
					continue
				res[status] += count
		return jsonify(res), 200
	except Exception as e:
		print(e)
		return jsonify({
			"error": e,
			"message": "Oops something went wrong"
		}), 500


def post_details_func(pid):
	try:
		db = client["users"]
		posts_collection = db["posts"]
		post = posts_collection.find_one({"_id": ObjectId(pid)})
		if post != None:
			post["_id"] = str(post["_id"])
			if(post['image']) == [""]: #code to change image if empty to empty list
					post['image'] = []
			return jsonify(post), 200
		else:
			return jsonify({
				"message": "Post not found"
			}), 404
	except Exception as e:
		print(e)
		return jsonify({
			"error": e,
			"message": "Oops! Something went wrong"
		}), 500

def adminlogout_func(sid):
	db = client["users"]
	# collection = db["adminDetails"]
	sessions_collection = db["sessions"]
	session_document = sessions_collection.find_one({"sid": sid})
	if session_document != None:
		sessions_collection.delete_one({"sid": sid})
		return jsonify({
			"message": "Log out success"
		}), 200
	else:
		return jsonify({
			"message": "User not found"
		}), 404

"""
█░█ █▀ █▀▀ █▀█
█▄█ ▄█ ██▄ █▀▄
"""
@app.route("/signup", methods=["POST"])
def signup():
	if request.method == "POST":
		name = request.form.get("name")
		phone = request.form.get("phone")
		if len(phone) != 10:
			return jsonify({
				"message" : "Enter a valid number"
			}), 422
		mail = request.form.get("mail")
		password = request.form.get("password")
		user_details = {
			"name": name,
			"phone": phone,
			"mail": mail,
			"password": password,
			"login_id": None,
			"isLoggedIn": False,
			"posts": []
		}
		signup_status = signup_func(user_details)
		return signup_status

@app.route("/otpverification", methods=["POST"])
def otpverification():
	if request.method == "POST":
		otp = request.form.get("otp")
		phone = request.form.get("phone")
		otp_verification_status = otp_verification_func(phone, otp)
		return otp_verification_status

@app.route("/login", methods=["POST"])
def login():
	if request.method == "POST":
		phone = request.form.get("phone")
		if len(phone) != 10:
			return jsonify({
				"message": "Enter a valid number"
			}), 422
		password = request.form.get("password")
		login_status = login_func(phone, password)
		return login_status

@app.route("/userinfo", methods=["GET"])
@auth_required
def userinfo():
	if request.method == "GET":
		phone = request.form.get("phone")
		userinfo_status = userinfo_func(phone)
		return userinfo_status

@app.route("/accountedit", methods=["POST"])
@auth_required
def accountedit():
	if request.method == "POST":
		phone = request.form.get("phone")
		username = request.form.get("name")
		accountedit_status = accountedit_func(username, phone)
		return accountedit_status

@app.route("/forgotpassword", methods=["POST"])
def forgotpassword():
	if request.method == "POST":
		phone = request.form.get("phone")
		forgotpassword_status = forgotpassword_func(phone)
		return forgotpassword_status

@app.route("/changepassword", methods=["POST"])
def changepassword():
	if request.method == "POST":
		phone = request.form.get("phone")
		otp = request.form.get("otp")
		password = request.form.get("password")
		changepassword_status = changepassword_func(phone, otp, password)
		return changepassword_status

@app.route("/userposts", methods=["GET"])
@auth_required
def userposts():
	if request.method == "GET":
		phone = request.form.get("phone")
		page = int(request.args["page"])
		userposts_status = userposts_func(phone, page)
		return userposts_status

@app.route("/getposts", methods=["GET"])
@auth_required
def getposts():
	if request.method == "GET":
		page = int(request.args.get("page"))
		getposts_status = getposts_func(page)
		return getposts_status

@app.route("/departmenttrans", methods=["POST"])
@auth_required
def departmenttrans():
	if request.method == "POST":
		pid=request.form.get("pid")
		category=request.form.get("category")
		s=dept_transfer(pid,category)
		return s

@app.route("/departments/<dept>", methods=["GET"])
def departments(dept):
	if request.method == "GET":
		if dept == "0":
			departments_status = departments_func()
			return departments_status
		else:
			departmentsprobs_status = departmentsprobs_func(dept)
			return departmentsprobs_status

@app.route("/uploadpost", methods=["POST"])
@auth_required
def uploadpost():
	if request.method == "POST":
		titles = request.form.get("title")
		description = request.form.get("description")
		images = request.form.get("images")
		category = request.form.get("category").capitalize()
		phone = request.form.get("phone")
		lat = request.form.get("lat")
		lon = request.form.get('lon')
		address = request.form.get('address')
		taluk = request.form.get("taluk")
		uploadpost_status = uploadpost_func(titles, description, images, category, phone, lat, lon, address, taluk)
		return uploadpost_status

@app.route("/like", methods=["POST"])
@auth_required
def like():
	if request.method == "POST":
		phone = request.form.get("phone")
		pid = request.form.get("pid")
		like_status = like_func(phone, pid)
		return like_status

@app.route("/logout", methods=["POST"])
@auth_required
def signout():
	if request.method == "POST":
		phone = request.form.get("phone")
		login_id = request.form.get("login_id")
		signout_status = logout_func(phone, login_id)
		return signout_status

"""
▄▀█ █▀▄ █▀▄▀█ █ █▄░█
█▀█ █▄▀ █░▀░█ █ █░▀█
"""
@app.route("/adminlogin", methods=["POST"])
def adminlogin():
	if request.method == "POST":
		mail = request.json["mail"]
		password = request.json["password"]
		ip = request.remote_addr
		adminlogin_status = adminlogin_func(mail, password, ip)
		return adminlogin_status

@app.route("/sidcheck", methods=["GET"])
@auth_required
def sidcheck():
	if request.method == "GET":
		sid = request.headers["WWW-Authenticate"]
		sidcheck_status = sidcheck_func(sid)
		return sidcheck_status

@app.route("/admingetposts", methods=["GET"])
@auth_required
def admingetposts():
	if request.method == "GET":
		page = int(request.args["page"])
		admingetposts_status = admingetposts_func(page)
		return admingetposts_status

@app.route("/editpost", methods=["PATCH"])
@auth_required
def edit_post():
	if request.method == "PATCH":
		pid = request.json.get("pid")
		category = request.json.get("category")
		taluk = request.json.get("taluk")
		status = request.json.get("status")
		remark = request.json.get("remark")
		to_update = {
			"category": category,
			"taluk": taluk,
			"status": status,
			"remark": remark
		}
		to_update = {key:value for (key, value) in to_update.items() if value != None}
		editpost_status = editpost_func(to_update, pid)
		return editpost_status

@app.route("/stats", methods=["GET"])
@auth_required
def stats():
	if request.method == "GET":
		stats_status = stats_func()
		return stats_status

@app.route("/monthinfo",methods=["GET"])
def monthinfo():
	if request.method =="GET":
		monthinfo_stats = monthinfo_func()
		return monthinfo_stats

@app.route("/list-categories", methods=["GET"])
def list_categories():
	return jsonify({
			"categories": ["Water", "Road", "Railways", "Electricity", "Education", "Medical", "Others"]
		}), 200

@app.route("/post-details", methods=["GET"])
@auth_required
def post_details():
	if request.method == "GET":
		args = request.args
		pid=args.get("pid", type=str)
		posts_detail_status = post_details_func(pid)
		return posts_detail_status

@app.route("/adminlogout", methods=["POST"])
@auth_required
def adminlogout():
	if request.method == "POST":
		sid = request.headers["WWW-Authenticate"]
		adminlogout_status = adminlogout_func(sid)
		return adminlogout_status

if __name__ == "__main__":
	# app.run(debug=True)
	app.run(debug=True)
