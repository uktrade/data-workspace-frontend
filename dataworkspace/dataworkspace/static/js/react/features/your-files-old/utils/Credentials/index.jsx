import AWS from 'aws-sdk';

class Credentials extends AWS.Credentials {
    constructor(credentialsUrl) {
        super();
        this.expiration = 0;
        this.credentialsUrl = credentialsUrl;
    }

    async refresh(callback) {
        try {
            const response = await (await fetch(this.credentialsUrl)).json();
            
            this.accessKeyId = response.AccessKeyId;
            this.secretAccessKey = response.SecretAccessKey;
            this.sessionToken = response.SessionTokken;
            this.expiration = Date.parse(response.Expiration);
        } catch (err) {
            callback(err);
            return;
        }

        callback();
    }

    needsRefresh() {
        return this.expiration - 60 < Date.now();
    }
}

export default Credentials;