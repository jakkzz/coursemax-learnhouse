// Actual custom pages/controls, synthetic HTTP, no native authentication or institutional traffic.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const expect=require((process.env.PLAYWRIGHT_MODULE_PATH||'playwright')+'/test').expect.configure({timeout:10000});
const output=process.env.LEARNHOUSE_UI_EVIDENCE,native=process.env.LEARNHOUSE_NATIVE_WEB;
assert(output&&native);
const nativeCss=fs.readdirSync(native+'/.next/static/chunks').filter(n=>n.endsWith('.css')).map(n=>fs.readFileSync(native+'/.next/static/chunks/'+n)).join('\n');
const server=http.createServer((req,res)=>{
 const p=new URL(req.url,'http://fixture').pathname;
 if(p==='/native.css'){res.setHeader('Content-Type','text/css');return res.end(nativeCss)}
 if(p==='/fixture.js'||p==='/fixture.css'){res.setHeader('Content-Type',p.endsWith('.css')?'text/css':'text/javascript');return res.end(fs.readFileSync(output+'/ui-public/CustomUiRepairs.'+(p.endsWith('.css')?'css':'js')))}
 if(p.startsWith('/_next/static/')){const f=path.resolve(native,'.next/static',p.slice('/_next/static/'.length));if(f.startsWith(path.resolve(native,'.next/static')+'/')&&fs.existsSync(f))return res.end(fs.readFileSync(f));res.statusCode=404;return res.end()}
 res.setHeader('Content-Type','text/html');res.end('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/native.css"><link rel="stylesheet" href="/fixture.css"></head><body style="margin:0;background:#fafafa;font-family:system-ui"><div id="root"></div><script type="module" src="/fixture.js"></script></body></html>');
});
function luminance(rgb){const a=rgb.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return .2126*a[0]+.7152*a[1]+.0722*a[2]}
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin=`http://127.0.0.1:${server.address().port}`;
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_BIN,args:['--disable-dev-shm-usage']});
 const results=[];
 try{
  const cases=[...['admin','student','staff','schedule','calendar','google','line'].flatMap(role=>[['en',1440,role],['th',390,role]]),['en',320,'admin']];
  for(const [lang,width,role] of cases){
   const th=lang==='th',t=(en,thai)=>th?thai:en,name=`${role}-${lang}-${width}`;
   const context=await browser.newContext({viewport:{width,height:900},timezoneId:'Asia/Bangkok',reducedMotion:'reduce'}),page=await context.newPage();
   const errors=[],unexpected=[],requests=[];let meReads=0,classReads=0,searches=0,version=1;
   const cls=()=>({id:20,course_id:role==='schedule'?null:10,course_uuid:role==='schedule'?'':'course_fixture',course_name:'Synthetic class ชั้นเรียนตัวอย่าง',course_available:false,academic_year:2569,semester:1,section:'P1',manageable:true,version,active_count:100,last_synced_at:'2026-11-04T02:00:00Z',registry_course_id:'100',registry_class_id:null});
   const official={registry_course_id:'100',registry_class_id:null,course_code:'990001',title:cls().course_name,section:'P1',teaching_pattern:'onsite',meetings:[{day:'Monday',start_time:'09:00',end_time:'12:00',details:'Synthetic room'}]};
   const calendars=[{id:1,name:'Synthetic school calendar',academic_year:2569,track:'Fixture',scope:'organization',can_edit:true,published_revision_id:10,latest_revision_id:10,has_teaching_weeks:false,planning_options:[{semester:1,program:'Fixture program',requires_plan:true,starts_on:'2026-08-01',ends_on:'2026-12-01',events:[]}]},{id:2,name:'Synthetic private calendar',academic_year:2568,track:'Fixture',scope:'teacher',can_edit:true,published_revision_id:11,latest_revision_id:11}];
   const review={id:1,created_at:'2026-11-04T03:00:00Z',status:'open',outcome:null,reason:'Synthetic review request',student_number:'6900000001',student_name:'Synthetic student นักศึกษาตัวอย่าง',match_state:'ready_to_match',decided_at:null,can_match:true,expected_token:'a'.repeat(64),accounts:[]};
   page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/*',async route=>{
    const req=route.request(),url=new URL(req.url());if(url.origin!==origin){unexpected.push(url.origin);return route.abort()}
    if(!url.pathname.startsWith('/api/'))return route.continue();
    const p=url.pathname,sub=p.replace('/api/v1/academic-classes','');requests.push({path:p,method:req.method(),body:req.method()==='POST'?req.postDataJSON():undefined});let data;
    if(p==='/api/v1/school-identity/me'){
     meReads++;
     if(role==='student'&&meReads===2)return route.fulfill({status:503,json:{detail:'Synthetic status outage'}});
     data={eligible:role!=='student',search_hint:'fixture',needs_google_signin:false,school_kind:role==='student'?'student':'staff',student_number_hint:role==='student'?'6900000001':null,directory_identity:role==='staff'||role==='student'?null:{officer_id:'fixture',name_th:'Synthetic teacher',name_en:'Synthetic teacher'},courses:[],student_match_status:role==='student'?'conflict':null,student_profile:null};
    }else if(p==='/api/v1/school-identity/search'){
     searches++;assert.equal(role,'staff','Student recovery must never search staff');
     if(searches===1)return route.fulfill({status:503,json:{detail:'Synthetic search outage'}});
     data={search_id:'synthetic',candidates:[]};
    }else if(p==='/api/v1/school-identity/timetable')data={academic_year:2569,semester:1,fetched_at:'2026-11-04T02:00:00Z',classes:[official]};
    else if(sub===''){
     classReads++;
     if(role==='admin'&&classReads===1)return route.fulfill({status:503,json:{detail:'Synthetic class outage'}});
     data={classes:role==='schedule'&&classReads===1?[]:[cls()],can_create:true,student_match_status:'matched'};
    }else if(sub==='/courses')data={courses:[{id:10,name:cls().course_name,private:true,registry_course_id:'100',course_code:'990001'}],teachers:[],can_assign_teachers:role==='admin'||role==='calendar',teaching_assignments:[]};
    else if(sub==='/connections/requests')data={requests:[],can_connect:false};
    else if(sub==='/connections/official-roster')data={students:[],fetched_at:'2026-11-04T02:00:00Z',source_url:'https://example.invalid/fixture'};
    else if(sub==='/20/roster')data={class_id:20,version,students:Array.from({length:100},(_,i)=>({id:i+1,student_number:String(6900000001+i),full_name_th:`Synthetic student นักศึกษาตัวอย่าง ${i+1}`,faculty:'Synthetic faculty',program:'Synthetic program',source:'registry',status:'active',account_status:'unlinked',missing_count:0})),events:[]};
    else if(sub==='/20/roster/refresh')data={class_id:20,class_version:version,control_version:0,paused:false,initial_review_required:false,status:role==='schedule'&&version===1?'needs_review':'ready',last_attempt_at:null,last_accepted_at:'2026-11-04T02:00:00Z',next_check_at:'2026-11-04T08:00:00Z',delayed:false,recent:[]};
    else if(sub==='/20/roster/preview')data={version,preview_id:'synthetic-preview',requires_large_drop_review:true,changes:[{kind:'missing_once',student_number:'6900000001',name:'Affected synthetic student'}],incoming_count:20,added_count:0,missing_count:80,withdraw_count:0,source_url:'https://example.invalid/fixture'};
    else if(sub==='/20/roster/apply'){assert.equal(req.postDataJSON().confirm_large_drop,true);assert.equal(req.postDataJSON().confirm_changes,true);version++;data={applied:true,version};}
    else if(sub.endsWith('/learning-access/status'))data={status:'ready',can_configure:false};
    else if(sub==='/20/identity-reviews')data={cases:[]};
    else if(sub==='/identity-reviews/own')data={can_request:role==='student',open_case_id:null,cases:[]};
    else if(sub==='/identity-reviews')data={cases:[review]};
    else if(sub==='/identity-reviews/1')data=review;
    else if(p==='/api/v1/school-calendars')data={can_edit:true,can_upload:true,calendars};
    else if(p==='/api/v1/school-calendars/schedules')data={class_id:20,version:1,manageable:true,revision_id:null,calendar_name:null,pattern:'onsite',school_pattern:'onsite',sessions:[]};
    else if(p==='/api/auth/line/capabilities')data={link:true};
    else if(p==='/api/auth/line/account')data={linked:false,can_manage:true};
    else {unexpected.push(p);return route.fulfill({status:404,json:{detail:'Unhandled synthetic endpoint'}})}
    return route.fulfill({json:data});
   });
   const surface=['student','staff'].includes(role)?'school':['google','line'].includes(role)?role:'classes';
   await page.goto(`${origin}/?surface=${surface}&lang=${lang}`);
   const result={name,checks:[]};
   try{
    if(role==='admin'){
     await expect(page.getByRole('alert')).toContainText(t('Classes could not be loaded','โหลดชั้นเรียนไม่ได้'));
     await expect(page.getByRole('tab',{name:t('NRRU classes','ชั้นเรียน NRRU'),exact:true})).toHaveAttribute('aria-selected','true');
     await page.getByRole('alert').getByRole('button',{name:t('Refresh','โหลดใหม่'),exact:true}).click();
     await expect(page.getByRole('alert')).toHaveCount(0);assert(classReads>=2);result.checks.push('visible class error and recovery on default tab');
     assert.equal(requests.filter(r=>r.path==='/api/v1/academic-classes/identity-reviews').length,0,'Inbox stays lazy');
     const inbox=page.getByRole('tab',{name:t('Identity reviews','ตรวจสอบตัวตน'),exact:true});
     await inbox.click();await page.getByRole('button',{name:t('Review request','ตรวจสอบคำขอ'),exact:true}).click();
     const note=page.getByLabel(t('Decision reason (administrator record)','เหตุผลการตัดสินใจ (บันทึกสำหรับผู้ดูแล)'),{exact:true});
     await note.fill('Keep this administrator draft');
     const classes=page.getByRole('tab',{name:t('LearnHouse classes','ชั้นเรียน LearnHouse'),exact:true});
     await classes.click();await expect(note).toBeHidden();await inbox.click();await expect(note).toHaveValue('Keep this administrator draft');
     assert.equal(requests.filter(r=>r.path==='/api/v1/academic-classes/identity-reviews/1').length,1);result.checks.push('review selection and draft retained without hidden refetch');
     await classes.click();await page.getByRole('button',{name:t('Manage roster','จัดการรายชื่อ'),exact:true}).click();
     const input=page.getByLabel(t('Search name, number or program','ค้นหาชื่อ รหัสนักศึกษา หรือสาขาวิชา'),{exact:true});
     await input.waitFor();
     const colors=await input.evaluate(e=>{const s=getComputedStyle(e);return {border:s.borderTopColor,background:s.backgroundColor}});
     const values=[luminance(colors.border),luminance(colors.background)].sort((a,b)=>b-a);result.contrast=(values[0]+.05)/(values[1]+.05);assert(result.contrast>=3);result.checks.push('computed enabled input boundary >=3:1');
     const trigger=page.getByRole('button',{name:t('Member actions','จัดการสมาชิก'),exact:true}).last();
     await trigger.click();const reason=page.getByLabel(t('Reason','เหตุผล'),{exact:true});await expect(reason).toBeFocused();
     const bounds=await reason.boundingBox();assert(bounds.y>=0&&bounds.y+bounds.height<=900,'Focused editor in viewport before any fill');
     await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:t('Withdraw member','ถอนสถานะสมาชิก'),exact:true})).not.toBeFocused();
     // With no reason, mutation controls are disabled; tab must reach the editor's Close action.
     await expect(page.getByRole('button',{name:t('Close','ปิด'),exact:true})).toBeFocused();
     await page.getByRole('button',{name:t('Close','ปิด'),exact:true}).click();await expect(trigger).toBeFocused();
     result.checks.push('100-row editor focus/visibility and close return');
     assert.equal(requests.filter(r=>r.method==='POST').length,0);
    }else if(role==='student'){
     const reason=page.getByLabel(t('Reason for review','เหตุผลที่ขอตรวจสอบ'),{exact:true});await reason.fill('Keep my student review draft');
     await page.getByRole('button',{name:t('Refresh','โหลดใหม่'),exact:true}).click();
     await page.getByRole('button',{name:t('Try again','ลองอีกครั้ง'),exact:true}).click();
     await expect(page.getByRole('alert')).toHaveCount(0);await expect(reason).toHaveValue('Keep my student review draft');
     assert.equal(meReads,3);assert.equal(searches,0);result.checks.push('status retry reloads own status and keeps draft');
    }else if(role==='staff'){
     await page.getByRole('button',{name:t('Find my NRRU name','ค้นหาชื่อของฉันในทะเบียนบุคลากร'),exact:true}).click();
     await page.getByRole('button',{name:t('Try again','ลองอีกครั้ง'),exact:true}).click();
     await expect(page.getByRole('heading',{name:t('No matching names found','ไม่พบชื่อที่ตรงกัน'),exact:true})).toBeVisible();
     assert.equal(searches,2);assert.equal(meReads,1);result.checks.push('staff search retries search, not status');
    }else if(role==='schedule'){
     await page.getByRole('button',{name:t('Open class: 990001 P1','ดูชั้นเรียน: 990001 P1'),exact:true}).click();
     const schedule=page.getByRole('radio',{name:t('Schedule','ตารางเรียน'),exact:true});await schedule.click();
     await page.getByRole('combobox',{name:t('School calendar','ปฏิทินการศึกษา'),exact:true}).selectOption('10');
     const date=page.getByLabel(t('First course week starts','วันเริ่มสัปดาห์แรกของรายวิชา'),{exact:true});await date.fill('2026-08-03');
     await page.getByRole('radio',{name:t('Details','รายละเอียด'),exact:true}).click();await expect(date).toBeHidden();
     await page.getByRole('radio',{name:t('Official roster','รายชื่อจากทะเบียน'),exact:true}).click();await expect(date).toBeHidden();
     await schedule.click();await expect(date).toHaveValue('2026-08-03');
     assert.equal(requests.filter(r=>r.path==='/api/v1/school-calendars/schedules').length,1);result.checks.push('schedule state retained across sibling views');
     await page.getByRole('button',{name:t('Review saved roster','ตรวจสอบรายชื่อที่บันทึกไว้'),exact:true}).click();
     await expect(page.locator('#saved-roster-title')).toBeFocused();assert(classReads>=2,'Fresh schedule class resolved without an internal ID field');
     await page.getByRole('button',{name:t('Review changes','ตรวจสอบการเปลี่ยนแปลง'),exact:true}).click();
     const apply=page.getByRole('button',{name:t('Apply roster','บันทึกรายชื่อ'),exact:true});await expect(apply).toBeDisabled();
     await page.locator('summary').filter({hasText:t('See affected students','ดูรายชื่อที่เปลี่ยนแปลง')}).click();
     await expect(page.getByText('Affected synthetic student',{exact:false})).toBeVisible();
     await page.getByRole('checkbox',{name:th?/ฉันตรวจสอบรายชื่อที่ลดลงมากนี้แล้ว/:/I reviewed this large drop/}).check();
     await apply.click();await expect(apply).toHaveCount(0);assert.equal(version,2);
     const writes=requests.filter(r=>r.method==='POST');assert.deepEqual(writes.map(r=>r.path),['/api/v1/academic-classes/20/roster/preview','/api/v1/academic-classes/20/roster/apply']);
     result.checks.push('canonical affected-student/large-drop review; exactly one explicit apply');
     await page.getByRole('button',{name:t('Back to class','กลับไปที่ชั้นเรียน'),exact:true}).click();await expect(date).toHaveValue('2026-08-03');await expect(page.locator('#real-class-title')).toBeFocused();
     result.checks.push('return from saved roster preserves schedule draft');
    }else if(role==='calendar'){
     await page.getByRole('tab',{name:t('School calendar','ปฏิทินการศึกษา'),exact:true}).click();
     await page.getByRole('combobox',{name:t('Academic year','ปีการศึกษา'),exact:true}).selectOption('2569');
     await page.getByRole('combobox',{name:t('Visibility','การใช้งาน'),exact:true}).selectOption('teacher');
     await expect(page.getByText(t('No calendars match these filters.','ไม่พบปฏิทินที่ตรงกับตัวกรอง'),{exact:true})).toBeVisible();
     await page.getByRole('button',{name:t('Clear filters','ล้างตัวกรอง'),exact:true}).click();
     await expect(page.getByRole('button',{name:t('View calendar','ดูปฏิทิน'),exact:true})).toHaveCount(2);
     await expect(page.getByRole('combobox',{name:t('Academic year','ปีการศึกษา'),exact:true})).toBeFocused();result.checks.push('localized filter no-match, clear and focus recovery');
    }else{
     const link=page.getByRole('link',{name:role==='google'?t('Cancel','ยกเลิก'):t('Back to account security','กลับไปที่ความปลอดภัยของบัญชี'),exact:true});
     await link.waitFor();const box=await link.boundingBox();assert(box.height>=44);result.touchHeight=box.height;result.checks.push('auth recovery target >=44px');
    }
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'No horizontal overflow');
    assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
    await page.screenshot({path:`${output}/${name}.png`,fullPage:false});results.push(result);console.log('PASS',name,result.checks.join('; '));
   }catch(error){await page.screenshot({path:`${output}/${name}-failed.png`,fullPage:true});throw error}
   finally{await context.close()}
  }
 }finally{await browser.close();server.close();fs.writeFileSync(output+'/ui-repairs-results.json',JSON.stringify(results,null,2))}
 assert.equal(results.length,15);
})().catch(error=>{console.error(error);server.close();process.exitCode=1});
