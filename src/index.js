require('dotenv').config();
const { Client, GatewayIntentBits, Events } = require('discord.js');

const client = new Client({ 
    intents: [
        GatewayIntentBits.Guilds, 
        GatewayIntentBits.GuildMembers, 
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.DirectMessages,
        GatewayIntentBits.GuildMessages,
    ],
    partials: ['MESSAGE', 'CHANNEL', 'REACTION'] // Required to receive DMs
});


// ========================================================================
// THIS FUNCTION ASK QUESTIONS TO THE USER IN DM TO SET UP USERNAME AND ROLE
// ========================================================================

client.on('guildMemberAdd', async member => {
    try {
        const dmChannel = await member.createDM();

        // Helper function to ask a question and await reply
        const askQuestion = async (question) => {
            await dmChannel.send(question);
            const filter = response => response.author.id === member.id;
            const collected = await dmChannel.awaitMessages({ filter, max: 1, time: 60000, errors: ['time'] });
            return collected.first().content;
        };

        // Ask for the user's name in a loop until a valid (non-empty) answer is provided
        let name = "";
        while (!name.trim()) {
            name = await askQuestion("Welcome to DUCS! I’m the DUCS Bot, here to help get you all set up on the server 🎉 Let’s start with a quick question — what’s your name?");
            if (!name.trim()) {
            await dmChannel.send("Please enter a valid name.");
            }
        }

        // Ask for the class year in a loop until a valid number is provided
        let classYear;
        const currentYear = new Date().getFullYear();
        while (true) {
            const classYearStr = await askQuestion("What's your class year?");
            classYear = parseInt(classYearStr.trim(), 10);
            if (!isNaN(classYear)) break;
            await dmChannel.send("Please enter a valid class year as a number.");
        }

        
        let email = "";
        while (true) {
            email = await askQuestion("What's your Denison email? (please include '@denison.edu' at the end)");
            if (email.trim().toLowerCase().endsWith('@denison.edu')) {
            break;
            } else {
            await dmChannel.send("Sorry, your email does not meet the required domain. Please try again.");
            }
        }

        let company = "";
        // If the member is a graduate, ask if they want to add their company name in their server nickname
        if (classYear < currentYear) {
            while (true) {
            const companyAnswer = await askQuestion("Since you are graduated, do you want to add your company name or school in your server nickname? If yes, please enter the company name, or type 'no' to skip.");
            if (!companyAnswer.trim()) {
                await dmChannel.send("Please enter a valid response.");
                continue;
            }
            if (companyAnswer.trim().toLowerCase() === 'no') {
                break;
            }
            company = companyAnswer.trim();
            break;
            }
        }

        // Build the new nickname based on the answers
        let nickname = "";
        if (classYear < currentYear) {
            // For graduates, include company name if provided
            nickname = `${name} - ${classYear}` + (company ? ` - ${company}` : "");
        } else {
            // For current students or incoming members
            nickname = `${name} - ${classYear}`;
        }

        // Attempt to set the nickname and assign the "Students/Alumni" role
        try {
            await member.setNickname(nickname);
            // Find the role "Students/Alumni" in the guild
            const role = member.guild.roles.cache.find(role => role.name === "Students/Alumni");
            if (role) {
                await member.roles.add(role);
                await dmChannel.send(`Success! Your nickname has been changed to: ${nickname} and you have been assigned the "Students/Alumni" role. Contact an admin if you want to change.`);
            } else {
                await dmChannel.send(`Nickname updated successfully to: ${nickname} but the role 'Students/Alumni' was not found.`);
            }
        } catch (err) {
            console.error('Failed to change nickname or assign role:', err);
            await dmChannel.send("I couldn't change your nickname or assign your role. Please contact an admin.");
        }
    } catch (error) {
        console.error('Error handling guild member join:', error);
    }
});


// ========================================================================
// THIS FUNCTION LISTENS TO MESSAGES IN THE CHANNELS "intern-process" AND "new-grad-process"
// AND REACTS TO THEM BASED ON THE CONTENT
// ========================================================================

client.on("messageCreate", message => {
    if (message.author.bot) return;
    if (!message.guild) return;
    if (message.channel.name !== 'intern-process' && message.channel.name !== 'new-grad-process') return;

    const pattern = /^!process\s+(.+?)\s+(apply|phone|OA|1st round|2nd round|final|offer|rejected|ghost)(?:\s+\((.+)\))?$/i;
    const match = pattern.exec(message.content);
    if (match) {
        message.react('✅').catch(console.error);
        if (match[2].toLowerCase() === 'offer') {
            message.channel.send(`Congrats 💐!`).catch(console.error);
        }
    } else {
        message.delete().catch(console.error);
        message.channel.send(`<@${message.author.id}>, please follow the format: "!process {company name} {apply|OA|phone|1st round|2nd round|final|offer|rejected|ghost}"`)
            .then(notice => {
                setTimeout(() => {
                    notice.delete().catch(console.error);
                }, 10000);
            });
    }
});

// ========================================================================
// This function iterates over all guild members,
// checks if their nickname indicates they are graduates,
// and if so, prompts them to update their company info.
// ========================================================================
client.on("messageCreate", async message => {
    if (message.author.bot || !message.guild) return;
    
    // Command format: !update-company <new company name>
    if (!message.content.toLowerCase().startsWith('!update-title')) return;

    // Helper to send a reply and schedule deletion of both messages
    const replyAndDelete = content =>
        message.reply(content)
            .then(reply => {
                setTimeout(() => {
                    reply.delete().catch(console.error);
                    message.delete().catch(console.error);
                }, 5000);
            });

    try {
        // Extract the new company name, if provided
        const args = message.content.split(' ').slice(1);
        const newCompany = args.join(' ').trim();
        
        // Ensure the command is used in a guild and by a member with a nickname
        const member = message.member;
        if (!member || (!member.nickname && !member.user.username)) {
            return replyAndDelete("Unable to determine your name from your profile.");
        }

        // Determine the current nickname (or username if no nickname exists)
        const currentName = member.nickname || member.user.username;

        // Expected nickname format: "Name - <year>" or "Name - <year> - <company>"
        const parts = currentName.split(" - ");
        
        // Extract and validate the year from the nickname
        const year = parseInt(parts[1].trim(), 10);
        if (isNaN(year)) {
            return replyAndDelete("Couldn't determine your graduation year.");
        }
        const currentYear = new Date().getFullYear();
        if (year > currentYear) {
            return replyAndDelete("This command is only available to graduates or those graduating this year.");
        }
    
        // Build the updated nickname:
        // Retain the original name and graduation year, and update company if provided.
        const updatedNickname = `${parts[0].trim()} - ${year}` + (newCompany ? ` - ${newCompany}` : "");

        await member.setNickname(updatedNickname);
        return replyAndDelete(`Your nickname has been updated to: ${updatedNickname}`);
    
    } catch (err) {
        console.error('Error updating company name:', err);
        return replyAndDelete("I couldn't update your nickname. Please contact an admin.");
    }
});



// Log the bot in
client.login(process.env.DISCORD_TOKEN);