from flask import Flask, request, jsonify
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import httpx
import gzip
import clan_pb2

app = Flask(__name__)

KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

BASE_URLS = {
    "IND": "https://client.ind.freefiremobile.com/",
    "ID": "https://clientbp.ggpolarbear.com/",
    "BR": "https://client.us.freefiremobile.com/",
    "ME": "https://clientbp.ggpolarbear.com/",
    "VN": "https://clientbp.ggpolarbear.com/",
    "TH": "https://clientbp.ggpolarbear.com/",
    "CIS": "https://clientbp.ggpolarbear.com/",
    "BD": "https://clientbp.ggpolarbear.com/",
    "PK": "https://clientbp.ggpolarbear.com/",
    "SG": "https://clientbp.ggpolarbear.com/",
    "SAC": "https://client.us.freefiremobile.com/",
    "TW": "https://clientbp.ggpolarbear.com/",
    "US": "https://client.na.freefiremobile.com/",
    "NA": "https://client.na.freefiremobile.com/"
}

def varint(n: int) -> bytes:
    result = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            b |= 0x80
        result.append(b)
        if not n:
            break
    return bytes(result)

def build_clan_members_request(clan_id: int) -> bytes:
    return varint(0x08) + varint(clan_id)

def encrypt_request(data_bytes: bytes) -> bytes:
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    return cipher.encrypt(pad(data_bytes, 16))

def maybe_decompress(data: bytes) -> bytes:
    if data[:2] == b'\x1f\x8b':
        return gzip.decompress(data)
    return data

@app.route('/clan_members', methods=['GET', 'POST'])
def clan_members():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    token = data.get('token')
    clan_id = data.get('clan_id')
    region = data.get('region', 'IND').upper()

    if not token:
        return jsonify({"success": False, "message": "Missing token"}), 400
    if not clan_id:
        return jsonify({"success": False, "message": "Missing clan_id"}), 400
    try:
        clan_id = int(clan_id)
    except ValueError:
        return jsonify({"success": False, "message": "clan_id must be integer"}), 400

    base_url = BASE_URLS.get(region)
    if not base_url:
        return jsonify({"success": False, "message": f"Invalid region: {region}"}), 400

    req_bytes = build_clan_members_request(clan_id)
    encrypted = encrypt_request(req_bytes)
    url = base_url + "GetClanMembers"

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Unity-Version": "2022.3.47f1",
        "ReleaseVersion": "OB53",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "UnityPlayer/2022.3.47f1 (UnityWebRequest)",
        "Host": base_url.split("//")[1].rstrip("/"),
        "Accept-Encoding": "gzip, deflate",
        "X-GA": "v1 1",
    }

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(url, headers=headers, content=encrypted)
            if resp.status_code != 200:
                error_msg = f"HTTP {resp.status_code}"
                try:
                    text = resp.content.decode('utf-8').strip()
                    if text:
                        error_msg = text
                except:
                    pass
                return jsonify({"success": False, "message": error_msg}), resp.status_code

            content = maybe_decompress(resp.content)
            response_proto = clan_pb2.GetClanMembersResponse()
            response_proto.ParseFromString(content)

            leader = None
            acting_leader = None
            officers = []
            members = []

            for entry in response_proto.entries:
                role_code = entry.role
                member_data = {
                    "uid": str(entry.info.uid),
                    "name": entry.info.name,
                    "total_glory": entry.total_glory,
                    "weekly_glory": entry.weekly_glory
                }
                if role_code == 3:
                    leader = member_data
                elif role_code == 4:
                    acting_leader = member_data
                elif role_code == 2:
                    officers.append(member_data)
                else:
                    members.append(member_data)

            return jsonify({
                "success": True,
                "clan_id": clan_id,
                "leader": leader,
                "acting_leader": acting_leader,
                "officers": officers,
                "members": members,
                "total_members": len(response_proto.entries)
            })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)