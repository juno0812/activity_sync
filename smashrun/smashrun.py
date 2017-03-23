import sys
import sqlite3
import requests

class Smashrun:
    """Handles connecting to the Smashrun API, downloading data, and storing data in the database.
    
    :param access_token: String of the user's access token to the API.
    """
    def __init__(self, access_token=''):
        self.access_token = access_token
        self.conn = None
        self.cursor = None

    
    def getActivitiesIds(self):
      """Return list of activity IDs from Smashrun."""
      ret = []

      if self.access_token is None:
        print('[!] no access token')
        return None

      endpoint = 'https://api.smashrun.com/v1/my/activities/search/ids'

      page = 0
      params = (('access_token', self.access_token),
                ('page',page),
                ('count',100))
      idsRes = requests.get(endpoint, params=params)
      if idsRes.status_code != requests.codes.ok:
          print('[!] problem getting ids with status code: {status} and page: {page}'.format(status=idsRes.status_code, page=page))
          return None

      ids = idsRes.json()
      while len(ids) != 0:
        ret = ret + ids
        page = page + 1
        params = (('access_token', self.access_token),
                ('page',page),
                ('count',100))
        idsRes = requests.get(endpoint, params=params)
        if idsRes.status_code != requests.codes.ok:
          print('[!] problem getting ids with status code: {status} and page: {page}'.format(status=idsRes.status_code, page=page))
          break

        ids = idsRes.json()

      print('[>] retreived ' + str(len(ret)) + ' IDs from Smashrun')

      return ret

    def determineDownload(self, ids):
      """Return a list of IDs that are not downloaded and need to be."""
      if self.cursor is None:
        print('[!] no cursor, check database connection')
        return False
      
      ret = []

      for id in ids:
        if not self.inActivitiesDb(id):
          ret.append(id)

      print('[>] need to download ' + str(len(ret)) + ' activities from Smashrun')
      return ret

    def inActivitiesDb(self, id):
      """Return whether or not an ID is already in the database."""
      self.cursor.execute("SELECT * FROM smashrun_activities where activity_id={act_id}".\
                    format(act_id=id))
      id_exists = self.cursor.fetchone()
      if id_exists:
        print('[>] id {cur_id} exists'.format(cur_id=id))
        return True

      print('[>] id {cur_id} does not exist'.format(cur_id=id))
      return False

    def initDb(self):
      """Initialize the database with three smashrun tables."""
      try:
        self.conn = sqlite3.connect('results_sync.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute('CREATE TABLE IF NOT EXISTS smashrun_activities (id INTEGER PRIMARY KEY AUTOINCREMENT, activity_id INTEGER UNIQUE)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS smashrun_activities_route (id INTEGER PRIMARY KEY AUTOINCREMENT, activity_id INTEGER, idx INTEGER, distance REAL, latitude REAL, longitude REAL, elevation REAL, heartRate REAL, clock REAL, FOREIGN KEY(activity_id) REFERENCES smashrun_activities(activity_id))')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS smashrun_activities_details (id INTEGER PRIMARY KEY AUTOINCREMENT, activityId INTEGER UNIQUE, activityType TEXT, duration REAL, distance REAL, calories INTEGER, notes TEXT, startDateTimeLocal TEXT, externalId TEXT, source TEXT, appVersion TEXT, deviceType TEXT, hasDetails BOOLEAN, hasDetailsGPS BOOLEAN, startLatitude REAL, startLongitude REAL, heartRateMax INTEGER, heartRateMin INTEGER, heartRateAverage INTEGER, weatherType TEXT, temperature, REAL, humidity INTEGER, windSpeed INTEGER, temperatureApparent REAL, temperatureWindChill REAL, howFelt TEXT, terrain TEXT, isRace BOOLEAN, isTreadmill BOOLEAN, syncDateTimeUTC TEXT, dateCreatedUTC TEXT, dateUpdatedUTC TEXT, speedVariability REAL, sunriseLocal TEXT, sunsetLocal TEXT, moonPhase REAL, elevationGain INTEGER, elevationLoss INTEGER, elevationAscent INTEGER, elevationDescent INTEGER, elevationMin INTEGER, elevationNet INTEGER, countryCode TEXT, country TEXT, city TEXT, state TEXT, isCooperTest BOOLEAN, FOREIGN KEY(activityId) REFERENCES smashrun_activities(activity_id))')
        self.conn.commit()
      except:
        print('[!] problem initializing db')
        print("Unexpected error:", sys.exc_info()[0])
        self.conn.close()
        return False
      return True
    
    def closeDb(self):
      self.conn.commit()
      self.conn.close()

    def downloadActivities(self, ids):
      """Download activity data (GPS and details) given a list of IDs."""
      for id in ids:
        endpoint = 'https://api.smashrun.com/v1/my/activities/{cur_id}'.format(cur_id=id)
        #params = (('access_token', access_token),)
        params = {'access_token':self.access_token}
        print('[>] attempting to download {cur_id}'.format(cur_id=id))

        activityRes = requests.get(endpoint, params=params)
        #print('status code = {status_code}'.format(status_code=activityRes.status_code))

        if activityRes.status_code != requests.codes.ok:
          print('[!] bad status code - {status}'.format(status=activityRes.status_code))
          continue

        activity = activityRes.json()
        #print(activity)
        #return False
        #print('[>] activity {activityId} - elevationLoss: {elevation}'.format(activityId=id, elevation=activity['elevationLoss']))

        if not self.storeActivity(activity):
          print('[!] problem storing activity {id}'.format(id=id))
        else:
          print('[>] stored activity {id}'.format(id=id))

      return True

    def storeActivity(self, activity):
      """Store activity details and GPS data in the database (all three tables) given a single activity."""
      if activity['hasDetailsGPS'] == 0:
        print('[!] this activity doesn\'t have GPS data, so skip that crap')
        print('[!]   activityId: {id}, date {date}, distance: {distance}'.format(id=activity['activityId'], date=activity['dateCreatedUTC'], distance=activity['distance']))
        return False

      ignoredKeys = ('recordingKeys', 'recordingValues', 'pauseIndexes', 'laps', 'songs', 'heartRateRecovery')

      sql = 'INSERT INTO smashrun_activities (activity_id) VALUES (?)'
      activityValues = (activity['activityId'],)
      try:
        self.cursor.execute(sql, activityValues)
      except:
        print('[!] problem inserting activity {id} with statement: {sql}'.format(id=activity['activityId'], sql=sql))
      newId = self.cursor.lastrowid

      # build statement for inserting into details table
      activityDetails = ()
      sql = 'INSERT INTO smashrun_activities_details ('
      firstOne = True
      for key in activity:
        if key in ignoredKeys:
          continue

        if firstOne:
          sql = sql + key
          firstOne = False
        else:
          sql = sql + ', ' + key

        activityDetails = activityDetails + (activity[key],)

      # have to include the proper number of '?' for values
      sql = sql + ') VALUES ('
      firstOne = True
      for x in range(0, len(activity) - len(ignoredKeys)):
        if firstOne:
          sql = sql + '?'
          firstOne = False
        else:
          sql = sql + ',?'

      sql = sql + ')'

      print('len of activityDetails = {len1} while expecting = {len2}'.format(len1=len(activityDetails), len2=(len(activity)-len(ignoredKeys))))

      try:
        self.cursor.execute(sql, activityDetails)
      except:
        print('[!] problem inserting activity {id} with statement: {sql}'.format(id=activity['activityId'], sql=sql))
        print("Unexpected error:", sys.exc_info()[0])
        return False

      distanceIndex = -1
      latitudeIndex = -1
      longitudeIndex = -1
      elevationIndex = -1
      heartRateIndex = -1
      clockIndex = -1
      # now time to insert the route
      keyIndex = 0
      for recordingKey in activity['recordingKeys']:
        if recordingKey == 'distance':
          distanceIndex = keyIndex
        elif recordingKey == 'latitude':
          latitudeIndex = keyIndex
        elif recordingKey == 'longitude':
          longitudeIndex = keyIndex
        elif recordingKey == 'elevation':
          elevationIndex = keyIndex
        elif recordingKey == 'heartRate':
          heartRateIndex = keyIndex
        elif recordingKey == 'clock':
          clockIndex = keyIndex
        keyIndex = keyIndex + 1

      sql = 'INSERT INTO smashrun_activities_route (activity_id, idx, distance, latitude, longitude, elevation, heartRate, clock) VALUES (?,?,?,?,?,?,?,?)'
      for x in range(0, len(activity['recordingValues'][0])):
        routeParam = (activity['activityId'], x, activity['recordingValues'][distanceIndex][x], activity['recordingValues'][latitudeIndex][x], activity['recordingValues'][longitudeIndex][x], activity['recordingValues'][elevationIndex][x], activity['recordingValues'][heartRateIndex][x], activity['recordingValues'][clockIndex][x])
        try:
          self.cursor.execute(sql, routeParam)
        except:
          print('[!] problem inserting activity {id} with statement: {sql}'.format(id=activity['activityId'], sql=sql))
          print("Unexpected error:", sys.exc_info()[0])
          return False
      return True

# https://api.smashrun.com/v1/my/activities?access_token=____37054-SkeuuA4bVjGpMXxIBfaF9UXvQEljAtmfsNA75KVOFE
